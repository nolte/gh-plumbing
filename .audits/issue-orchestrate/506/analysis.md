---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "506"
classification: "security"
secondary-classes: ["bug"]
route: "direct"
status: draft
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

## Dispatch log
