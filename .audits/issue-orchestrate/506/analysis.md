---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "506"
classification: "security"
secondary-classes: ["bug"]
route: "direct"
status: approved
created: "2026-11-20"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #506 — Reusable workflows write caller- and draft-controlled text into the step summary as markdown
- **URL**: https://github.com/nolte/gh-plumbing/issues/506
- **Labels**: cicd, security
- **Linked items**: #492, #505 (the class sweep that found it); no linked PR (`closedByPullRequestsReferences: []`)
- **Prior art checked**: `gh pr list --state all --search 506` returned `[]`; no `project/requirements/` artefact for the issue; `scripts/workflow_command_masking.py:112-114` names `$GITHUB_STEP_SUMMARY` under "Not covered"
- **Working copy**: `~/repos/.worktrees/gh-plumbing/506-step-summary-markdown`, branch `fix/506-step-summary-markdown` off `origin/develop` @ `cc1a67a`; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Requirements gate**: operator override, 2026-11-20 — `requirements-elicit` skipped; the issue carries its own acceptance criteria and the one open decision was taken at the gate (see Scope)
- **Decomposition**: inline (fallback); the issue surface was already read line by line for the cause verification, so `implementation-plan-author` would have repeated it

## Classification

- **Primary class**: security
- **Secondary class(es)**: bug
- **Rationale**: controlled text reaches a markdown renderer unescaped (content injection into the run's summary page: links, headings, images, mentions); no command execution. Confirmed by the operator 2026-11-20.
- **Asserted cause verified**: confirmed with one correction, read at `cc1a67a`:
  - **established** — `reusable-release-publish.yml:738` writes `${title:-_(empty)_}` raw into a table cell; `:749-751` writes `body_head` inside a fixed three-backtick fence.
  - **established** — `reusable-release-cd-refresh-master.yml:254-258` and `:285-291` write `MODE`, `FROM_REF`, `TARGET`, `SOURCE_SHA`, `EXPECTED`, `msg` into the summary; `FROM_REF`/`TARGET` are caller inputs (`:184-185`, `:269-270`).
  - **refuted (part)** — the issue says "API error text in the summary blocks". `REASON` is assigned only from literals (`:153-165`); the API response `$out` goes to the log (`:235`), not to the summary. No API error text reaches the summary in this workflow.
  - **established** — `reusable-nodejs-coverage.yaml:106-108` interpolates `total[k].pct`, `.covered`, `.total` from the consumer's JSON into table rows.
  - **established** — `reusable-python-coverage.yaml:82` appends `coverage report --format=markdown` unfiltered. **Unestablished**: whether coverage.py escapes file names in that format; reading `coverage/report.py` of the pinned version would settle it. Not load-bearing: the policy below treats command output as controlled either way.
  - **established, not in the issue** — `reusable-release-archive.yml:350` and `:389` write asset file names (`${files[@]##*/}`, repository-controlled) and `$TAG` in backtick spans.

## Scope

- **In scope**:
  - One writing rule for controlled text in a step summary, decided by the operator 2026-11-20: **encode, then wrap**. A canonical helper turns control characters into `?` and every ASCII punctuation character into its numeric HTML entity; a single-line value goes inside `<code>…</code>`, multi-line text inside `<pre>…</pre>` (line ends kept). No computed fence, no backslash escapes.
  - Apply it to every summary write of the reusable workflows (sweep below), including `reusable-release-archive.yml`.
  - The guard `scripts/workflow_command_masking.py` gets the rule for `$GITHUB_STEP_SUMMARY`, with tests; its "Not covered" entry goes.
  - Documentation that describes the summary format (`docs/en/workflows/coverage.md:8,26`, `docs/de/workflows/coverage.md:26`) follows if the rendered form changes.
- **Out of scope**:
  - Non-reusable workflows (the guard's selector excludes them today; unchanged).
  - `${{ … }}` expressions in `run:` bodies (neighbouring class, named in the guard's docstring).
  - The log and `$GITHUB_OUTPUT` channels (#505).

**Basis of the rule** — measured 2026-11-20 with `gh api markdown -f mode=gfm -f context=nolte/gh-plumbing`:

- **established** — entity-encoded `[x](https://example.com) *b* `` `c` `` | <img src=x>` in a table cell renders as literal text, one cell; `https&#58;//example.com` and `www&#46;example&#46;com` do not autolink.
- **established** — `&#64;octocat` and `&#35;1` in a plain cell still become a mention and an issue link; inside `<code>` and `<pre>` they do not.
- **established** — inside `<pre>`, encoded content with a blank line, a `#` line and a three-backtick line stays one inert block.
- **unestablished** — that the step-summary renderer behaves like the `/markdown` endpoint. A dry run of `reusable-release-publish.yml` against a draft with a hostile title and body would settle it; not made (it needs a draft release on a repository and a workflow run). P2's acceptance carries the endpoint probe; the PR's Risk notes carry this gap.

**Sweep** (predicate: `grep -rnE 'GITHUB_STEP_SUMMARY|core\.summary|summary\.addRaw' .github/workflows .github/actions actions`, at `cc1a67a`): 16 lines in 5 of 28 reusable workflows; 0 in `actions/setup-vale`.

| File | Lines | Interpolated values to classify |
|---|---|---|
| `reusable-release-publish.yml` | 348, 600, 620, 633, 752, 843, 851, 1091, 1104, 1142 | `actual`, `TAG`, `new_sha`, `msg`, `title`, `TARGET_SHA`, `created_at`, runner variables, `VBF_SOURCE`, `VBF_COUNT`, `DRY_RUN`, `body_head`, `shown_filename`, `published_at` |
| `reusable-release-cd-refresh-master.yml` | 259, 292 | `MODE`, `action`, `FROM_REF`, `SOURCE_SHA`, `TARGET`, `EXPECTED`, `msg`, `REASON` |
| `reusable-release-archive.yml` | 350, 389 | `files[@]`, `TAG` |
| `reusable-nodejs-coverage.yaml` | 84 | `total[k].pct`, `.covered`, `.total` |
| `reusable-python-coverage.yaml` | 83 | output of `coverage report` |

## Route

- **Decision**: direct
- **Rationale**: one outcome (controlled text can't alter summary rendering), one PR strand, no roadmap item.

## Work packages

### P1 — Enumerate the summary surface

- **Problem statement**: Hypothesis: the sweep table above is the complete set of summary writes in the guard's selector, and each interpolated value is either controlled (caller input, draft or API response, repository or consumer content, command output) or constant/numeric by construction. The package checks both independently of the orchestrator's reading.
- **Acceptance criteria**: a list of every summary write (`file:line`) with each interpolated name, its origin (`file:line` of the assignment or `env:` entry) and a verdict controlled / constant / numeric / format-checked; any write the table misses is named; any value the table would mis-class is named with the line that shows it.
- **Touched files / artifacts**: none (read-only)
- **Specialist**: `nolte-engineering:code-security-reviewer` (read-only audit with file:line attribution; Read/Grep/Glob only, so nothing in the brief needs a shell)
- **Depends on**: none

### P2 — Apply the rule and guard it

- **Problem statement**: Hypothesis: one canonical helper per language (bash, Node; Python where a heredoc writes the summary) plus the `<code>`/`<pre>` wrap repairs every controlled write P1 lists, and the guard's existing name analysis (masked / refused / constant / numeric / ALLOWED) can carry a summary sink whose only accepted mask is that helper.
- **Acceptance criteria**:
  1. Every controlled value on a summary line goes through the canonical encoder and sits inside `<code>` or `<pre>`; command output written to a summary (`coverage report`) is treated as controlled multi-line text. No controlled value remains inside a backtick span or fence.
  2. `python3 scripts/workflow_command_masking.py` exits 0 on the tree and non-zero on the `origin/develop` copy of each of the five workflows (red before, green after).
  3. The guard refuses, with a fixture test each: a raw interpolation on a summary line, a value masked only by `shown`, a `{ …; } >> "$GITHUB_STEP_SUMMARY"` group line, a Node heredoc redirected to the summary, and unfiltered command output appended to the summary — or, for any of these it can't see, the docstring's "Not covered" list says so. The three existing tests that assert a summary write is no finding (`scripts/tests/test_workflow_command_masking.py:91,116,273`) are replaced, not deleted without successor.
  4. A test runs the bash helper and the Node helper on a hostile value (backticks, `|`, line end, `</pre>`, `[x](u)`, `<img>`, `@name`, `#1`, `&`) and asserts the output contains no ASCII punctuation outside `&#…;` sequences and no control character other than the line ends `<pre>` keeps.
  5. The helper's output for that hostile value, wrapped as a table cell and as a `<pre>` block, is rendered once through `gh api markdown -f mode=gfm` and the returned HTML shows no `<a`, `<img`, `<h1`–`<h6` and no second table cell from the value; the command and output are returned in the result (not a CI test).
  6. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest scripts/tests -q` passes; `pre-commit run --all-files` passes; the new test file, if any, is added to `build-static-tests.yaml:155`.
  7. `docs/en/workflows/coverage.md` and `docs/de/workflows/coverage.md` describe the summary as rendered after the change; the guard docstring no longer lists `$GITHUB_STEP_SUMMARY` under "Not covered".
- **Touched files / artifacts**: `.github/workflows/reusable-release-publish.yml`, `reusable-release-cd-refresh-master.yml`, `reusable-release-archive.yml`, `reusable-nodejs-coverage.yaml`, `reusable-python-coverage.yaml`, `scripts/workflow_command_masking.py`, `scripts/tests/test_workflow_command_masking.py` (and a new test file if the helper test doesn't fit there), `.github/workflows/build-static-tests.yaml`, `docs/en/workflows/coverage.md`, `docs/de/workflows/coverage.md`
- **Specialist**: `nolte-engineering:fullstack-developer` (runnable code plus matching tests against the repository's own stack; the helper text and the guard's canonical-form constant have to be written together, so the workflows and the guard stay one package)
- **Depends on**: P1

Verification (operation 6, not a package): security-briefed read-only diff review by an agent that didn't write the change, plus `nolte-shared:cicd-pipeline-reviewer` on the five workflows for untrusted-input handling.

## Existing installations / upgrade / rollback

Health gate: none (reusable workflows and a guard script, consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P2 | consumers on `@develop` get the new summary rendering on their next run; inputs, outputs, secrets and job names unchanged | none (reusable workflow); surfaces read: `workflow_call` inputs/outputs, job names used as required checks | reverting the commit restores the old rendering; summaries already written keep their form | `git diff origin/develop...HEAD -- .github/workflows` shows no change under `on:`, `inputs:`, `outputs:`, `secrets:` or a job `name:` |

P1: not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path.

## Dependency ordering

P1 → P2

## Risks

- **Renderer gap**: the rule is measured on the `/markdown` endpoint, not on a rendered summary. Mitigation: `<code>`/`<pre>` with entity-encoded content is plain HTML with no markdown-active character left; the gap is named in the PR.
- **Readability**: a Python coverage table becomes a `<pre>` block; titles lose nothing but sit in monospace. Mitigation: docs updated in P2; visible in the PR's Risk notes for consumers.
- **Guard false positives on consumers of the guard**: none — the guard only runs in this repository.
- **Security-sensitive path** (release workflows): `code-security-reviewer` scopes the surface in P1; a security-briefed read-only diff review runs before the PR. `security-review` is not used from this session (it is rooted in the primary checkout).
- **Release-publish is exercised only on a release**: a quoting mistake in the summary step would fail a publish run. Mitigation: `set -euo pipefail` paths reviewed in the diff review; acceptance 4 executes the helper itself.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| `scripts/docs_freshness.py:246-249` writes its report to the summary (called from `reusable-docs-freshness.yaml:87`, `reusable-release-publish.yml:1027`); repository file names and a raw doc line (`:185`) in it | specialist result (P1, refutes H1) | fix directly in P2 (same-pattern sibling; file added to P2's touched files) | `grep -n STEP_SUMMARY scripts/docs_freshness.py` | none |
| `scripts/branch_protection_audit.py:427-430` writes its report to the summary (called from `reusable-branch-protection-audit.yaml:101`, run from the caller's checkout); repo, branch, context names, `_extends` value in it | specialist result (P1, refutes H1) | fix directly in P2 (same-pattern sibling; file added to P2's touched files) | `grep -n STEP_SUMMARY scripts/branch_protection_audit.py` | none |
| `EXPECTED` at `reusable-release-cd-refresh-master.yml:217` may be more than one line (`git ls-remote` tail match) | specialist result (P1) | asserted, not reproduced; handed to P2 as a value to treat as controlled | settled by `git ls-remote` against a repo with a branch `x/refs/heads/<target>` | none |
| Intended markdown in values: `@` mention of the triggerer (`release-publish:742`), backticks in `REASON` (`refresh-master:153`), `_(empty)_` fallback (`:738`) | specialist result (P1) | handed to P2: constants stay as written; the actor stays a mention as a runner-provided login, on the guard's ALLOWED list with that reason | `file:line` as named | none |
| F1 BLOCKING: an address inside `<code>` autolinks despite entities (`<code>a&#64;b&#46;co</code>` → `<a href="mailto:a@b.co">`); all three encoders | diff review @ 2b49da4 (security lane) | fix directly (back to P2 specialist) | `gh api markdown -f mode=gfm -F text=@p2.md`, re-run by the orchestrator: base row links, `<span>&#64;</span>` and `&#64;<!-- -->` rows don't | none |
| F2: guard passes summary writes via `done >>`/`fi >>`, `\| tee -a`, a second redirect on the line, `{` sharing a line with a statement, control-flow reassignment, Python `end=`/`sep=`, later redefinition of `md_*` — none on "Not covered" | diff review @ 2b49da4 (security lane) | fix directly: close or list each (back to P2 specialist) | reviewer fixtures d04–d06, b06–b09, b14–b18, b21, b35, b39, b40, b42, d14, d20, d27 through `audit()` | none |
| F3/N1: `reusable-python-coverage.yaml:88` loses the report from summary and log when `coverage report` exits non-zero | diff review @ 2b49da4 (both lanes) | fix directly (back to P2 specialist) | stub exiting 2: head rc=2 with empty summary, base rc=2 with table | none |
| N3: comment at `reusable-release-publish.yml:636` says the log line masks `msg`; `:635` prints it unmasked | diff review @ 2b49da4 (pipeline lane) | fix directly (back to P2 specialist) | `sed -n 635,637p` | none |
| N4: Node encoder test skips when `node` is missing (`test_step_summary_markdown.py:105`); the CI job provisions Python only | diff review @ 2b49da4 (pipeline lane) | fix directly (back to P2 specialist) | `grep -n skipif scripts/tests/test_step_summary_markdown.py` | none |
| F4: encoders differ on U+2028/2029, C1 under `LC_ALL=C`, invalid UTF-8; bidi and zero-width characters pass all three; comments say `?` where output is `&#63;` | diff review @ 2b49da4 (security lane) | fix directly where cheap (wording, C1), rest named in the docstring (back to P2 specialist) | reviewer runs under `C.UTF-8`/`LC_ALL=C` | none |
| F5: entity inflation may reach the 1 MiB summary limit earlier on very large coverage reports | diff review @ 2b49da4 (security lane) | not reproduced; into Risk / rollout notes; settled by a run with a ~600 KB report | none | none |
| Re-review: F1, F3, F4 and the reported F2 bypasses closed | diff review @ ba38066 (code state 9e44d00, security lane) | no action | reviewer runs on bash 5.1/5.2/5.3 and the render API | none |
| N1 BLOCKING: a closer on the line of the last statement (`echo "$V"; } >> "$GITHUB_STEP_SUMMARY"`) hides the whole group from the guard; regression from 9d198a9 | diff review @ ba38066 (security lane) | fix directly (back to P2 specialist) | fixture under scratchpad `n1/`, re-run by the orchestrator: guard rc=0 with a raw `$V` | none |
| N2: `function f {` … `} >> "$S"` and `done \|` + `tee -a "$S"` on the next line pass; path-in-variable and print aliases not listed for the summary | diff review @ ba38066 (security lane) | fix directly: close or list (back to P2 specialist) | reviewer fixtures v22b, v36, b02, d29, b16, b22, b26 | none |
| N3: bash `md_enc` is quadratic per line (40 000 chars: 7.1 s) | diff review @ ba38066 (security lane) | fix directly if a linear form stays byte-identical, else stated in the helper comment (back to P2 specialist) | reviewer timing on bash 5.2/5.3 | none |
| Third pass: N1, N2 closed; N3 closed for plain and mixed text (punctuation-dense lines stay quadratic: 160 000 × `-` 12.6 s on bash 5.2); new bash `md_enc` byte-identical to Python/Node over 720 values on bash 5.1.16/5.2.37/5.3.9 | diff review @ f985a5c (code state 2c2334a, security lane) | no action | reviewer runs | none |
| M1: a heredoc inside a group redirected to the summary is read by the log rule (`workflow_command_masking.py` ≈1257); `shown`-masked value passes; mirror false positive for a Python heredoc using `md_code` | diff review @ f985a5c (security lane) | fix directly (back to P2 specialist) | reviewer fixtures p11, p12, p12b, p13 through the CLI, rc=0 | none |
| M2: an array literal starting with a keyword (`kw=(if for while)`) counts as an opener and hides the line before it | diff review @ f985a5c (security lane) | fix directly or name under "Not covered" (back to P2 specialist) | reviewer fixture q08 | none |
| bash `md_enc` aborts under `set +B` (brace expansion); no step sets it | diff review @ f985a5c (security lane) | comment at the constant (back to P2 specialist) | `printf: {91..96}: invalid number` | none |
| #505 log rule reads a masked reassignment by line order, not control flow (masked assignment in a dead branch covers a raw one); same on `origin/develop` @ cc1a67a | specialist result (P2 fix round 1), re-run by the orchestrator on both guard versions | to file as its own issue after the green gate (operator go-ahead 2026-11-20); fails (b): the strict rule refuses `actions/setup-vale/setup-vale.sh:51-54` | fixture under scratchpad `logrule/`: both guards print "prints only masked or constrained values" | to file |
| stdout of a Python/Node heredoc redirected to `$GITHUB_OUTPUT` is not read by the guard (`node <<'NODE' >> "$GITHUB_OUTPUT"` with `console.log(`v=${p}`)`); same on `origin/develop` @ cc1a67a | specialist result (P2 fix round 3), re-run by the orchestrator on both guard versions | named under "Not covered"; pre-existing #505 rule, outside this issue's class — to file with the operator's go-ahead | fixture under scratchpad `envheredoc/`: both guards print "prints only masked or constrained values" | to file |

## Dispatch log

2026-11-20 P1 dispatched to nolte-engineering:code-security-reviewer — H1 refuted (16 shell writes complete; two Python scripts also write the summary), H2 confirmed; per-value origin table returned. Sweep total: 18 write sites (16 shell lines in 5 workflows + 2 scripts reached from 3 workflows). `scripts/required_check_triggers.py:515` writes too but no workflow calls it.
2026-11-20 P2 dispatched to nolte-engineering:fullstack-developer — hypothesis confirmed; commits ee41837, 888dcdb, 28a2a3b, fc6482b, 7a3f5a2; helpers `md_enc`/`md_code`/`md_pre` per language, guard carries the summary sink; two findings fixed directly (`head -c 800` cuts a UTF-8 character; stale comment at refresh-master:172-174). Gate re-run by the orchestrator at 7a3f5a2: guard exit 0, `471 passed`, pre-commit passed; actionlint without ShellCheck (shim has no version).
2026-11-20 P2 review fixes by nolte-engineering:fullstack-developer — commits 5559eda, 766572e, 4ea1b35, 9d198a9, 9e44d00; F1 closed with `@` → `&#64;<!-- -->`, F2 closed except items now named under "Not covered", F3/N3/N4/F4 fixed; two #505 guard gaps closed alongside (`>&2` inside a file-redirected group, `>|` to `$GITHUB_OUTPUT`). Gate re-run by the orchestrator at 9e44d00: guard exit 0, `514 passed`, pre-commit passed. Re-review of 9e44d00 dispatched to the security lane.
2026-11-20 P2 second fix round by nolte-engineering:fullstack-developer — commits fa8e5e4 (N3: bash `md_enc` without a per-character loop), 2c2334a (N1, N2: group closer anywhere on its line; fail closed on a summary closer without an opener). Gate re-run by the orchestrator at 2c2334a: guard exit 0, `525 passed`, pre-commit passed; the N1 fixture is a finding again. Third review pass dispatched to the security lane (bash 5.1/5.2 for the rewritten helper).
2026-11-20 P2 third fix round by nolte-engineering:fullstack-developer — commit 90f7767 (M1 closed: heredoc inherits the summary destination of its group; M2 closed: same-line array literal opens nothing; `set +B` dependency stated at `SHELL_MD`). Delta 2c2334a..90f7767 touches only the guard and its test file. Gate re-run by the orchestrator at 90f7767: guard exit 0, `533 passed`, pre-commit passed. Narrow delta review dispatched to the security lane.
