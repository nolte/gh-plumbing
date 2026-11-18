---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "492"
classification: "security"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #492 — reusable-release-publish: older error lines print caller- and draft-controlled text raw
- **URL**: https://github.com/nolte/gh-plumbing/issues/492
- **Labels**: cicd, security
- **Linked items**: #484 / PR #491 (merged; introduced the masking, its diff review found this). `closedByPullRequestsReferences` is empty; no open PR.
- **Prior art checked**: masking pattern `${var//[[:cntrl:]]/?}` at `.github/workflows/reusable-release-publish.yml:244`, `:258`, `:961`; test harness `scripts/tests/test_release_publish_vale.py` (reads a step's `run:` body from the workflow and runs it under bash against stubs), run in CI by `build-static-tests.yaml:144-146`.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/492-mask-release-publish-messages`, branch `fix/492-mask-release-publish-messages` off `origin/develop` @ f4f1d99; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Caller**: `issue-backlog-partition` run `2026-11-18-2-gh-plumbing`, `lane: true` → ends at `committed-locally`. Develop-health re-read 2026-11-18T22:08Z: red only 25970095265 and 30715245456, both overridden by the operator in the caller's checkpoint.

## Classification

- **Primary class**: security (confirmed by the operator, 2026-11-18)
- **Secondary class(es)**: none
- **Rationale**: workflow-command injection through text a caller or a draft editor controls.
- **Asserted cause verified** (all line numbers at f4f1d99; the issue's are as of 078116b):
  - *Raw prints* — confirmed. `inputs.tag` reaches `:203` as `$TAG` before it matched any draft (`REQUESTED_TAG` at `:174`, `TAG="$REQUESTED_TAG"` at `:199`). Draft tag names are listed raw by `jq` at `:193` and `:204` (to stderr). `expected-target-sha` is printed raw at `:282`, exactly when it failed the `^[0-9a-f]{40}$` test. `$TAG` is printed in `::error::`/`::warning::`/`::notice::` lines at `:197`, `:209`, `:246`, `:251`, `:258`, `:297`, `:569`, `:756`, `:764`, `:874`, `:893`, `:926`, `:963`, `:967`, `:979`, `:1014`, and inside `$msg` at `:555-556`.
  - *Further carriers the issue doesn't name* — confirmed by reading: `inputs.asset-filename` as `$filename` at `:730`, `:756`, `:764`; `hacs.json`'s `.filename` (repository content at the target commit) as `$hacs_filename` at `:730` and as `$filename` when the input is empty; `$domain` (from `vbf.json`) at `:742`.
  - *"`$GITHUB_OUTPUT` only ever receives validated values"* — **refuted**. `:216` writes `tag=$TAG` with no check on its characters. On the explicit path `TAG` equals a draft's tag name (`:200`), on the resolved path it *is* one (`:196`); neither constrains its characters. A tag name carrying a line break would add output lines. `target_sha` (`:261`) is validated.
  - *A value with a line break followed by `::<command>::` is read as a workflow command* — unestablished here, taken from GitHub's documented runner behaviour; not reproduced on a runner (the issue says so too). Whether GitHub accepts a control character in a draft `tag_name` is unestablished; the observation that would settle it is creating such a draft through the API, which this run doesn't do. `inputs.tag` and `inputs.asset-filename` need no such assumption: a caller passes them.

## Scope

- **In scope**: `reusable-release-publish.yml` — validate the tag at its source, mask every remaining raw print of a caller-, draft- or repository-content-controlled value; a test that holds the class; the same predicate run over the other reusable workflows with the hit count recorded.
- **Out of scope**: repairing hits in other workflows beyond what finding triage (a)–(c) allows — anything larger is filed. No change to what the workflow publishes.

## Requirements gate

No artefact under `project/requirements/` covers #492. **Operator override, 2026-11-18:** `requirements-elicit` skipped; the issue states two testable acceptance criteria and the operator chose the approach (validate at the source, mask the rest).

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Scope the surface: the class across the reusable workflows (audit, read-only)

- **Problem statement**: the issue lists three carriers from a code read of one file. The fix and the guard need the enumerated class: every `::error::`, `::warning::`, `::notice::` line (and every `$GITHUB_OUTPUT` / `$GITHUB_ENV` / `$GITHUB_STEP_SUMMARY` write) in `.github/workflows/reusable-*.y*ml` and `actions/**/action.yml` that interpolates a value, with each value's origin: caller input, draft or API response text, repository content, or validated/constant.
- **Acceptance criteria**: a table of hits per file with `file:line`, the variable, its origin and whether it is constrained before the print; the predicate (the command or script that produced the list) stated so it can be re-run; a count for `reusable-release-publish.yml` and a count for the other files.
- **Touched files / artifacts**: none (read-only).
- **Specialist**: `nolte-engineering:code-security-reviewer`, scoped to this class and these paths (step one of the audit → fix → verify chain).
- **Depends on**: none

### P2 — Validate the tag at its source and mask the remaining prints

- **Problem statement**: hypothesis — once "Resolve draft" refuses a tag that contains a control character before writing it to `$GITHUB_OUTPUT`, every later `$TAG` is clean by construction, and only the prints that happen before or outside that validation need masking.
- **Acceptance criteria**:
  1. "Resolve draft" exits non-zero, before `:216`'s write, when the tag (given or resolved from a draft) contains a control character; its message prints the tag masked. Shown by a test that runs the step's `run:` body with such a tag and asserts no output line starts with `::` other than the one intended `::error::`, and that `$GITHUB_OUTPUT` stays empty.
  2. The pre-match print of `inputs.tag`, both `jq` listings of draft tag names, `expected-target-sha` at `:282`, and the `asset-filename` / `hacs.json` / `$domain` prints mask control characters the way `:244` does. Each shown by a test with a line break plus `::warning::x` in the value.
  3. A clean tag behaves as before: the existing tests in `scripts/tests/` pass unchanged.
  4. Every P1 hit in `reusable-release-publish.yml` is either repaired or shown constrained, one line each.
- **Touched files / artifacts**: `.github/workflows/reusable-release-publish.yml`, `scripts/tests/test_release_publish_*.py` (new file for these cases), `.github/workflows/build-static-tests.yaml` only if a new test file has to be named in `pytest-args`.
- **Specialist**: `nolte-engineering:fullstack-developer` (workflow shell plus pytest; no candidate names GitHub Actions workflow authoring as an implementing responsibility — `cicd-pipeline-design` designs pipelines, it doesn't patch one step).
- **Depends on**: P1

### P3 — Class guard

- **Problem statement**: the next message added to a reusable workflow can print a raw value again; #491 fixed one line and left the rest.
- **Acceptance criteria**: a test in `scripts/tests/` enumerates every workflow-command line in `reusable-release-publish.yml` from the file itself (not a list of line numbers) and fails when one interpolates a variable that is neither masked at the print nor on a short, commented allow-list of values validated or constant by construction. It fails on the pre-fix file (shown by running it against `git show origin/develop:…`) and passes on the fixed one. Whether it can cover all reusable workflows in this change depends on P1's count: if the other files have hits that aren't repaired here, the guard covers this file and the remainder is filed with the count.
- **Touched files / artifacts**: `scripts/tests/test_workflow_command_masking.py` (name at the specialist's discretion), `build-static-tests.yaml` as in P2.
- **Specialist**: `nolte-engineering:fullstack-developer`, same dispatch as P2.
- **Depends on**: P2

### Verify (operation 6, not a package)

`pytest scripts/tests`, `pre-commit` on the changed files, `actionlint` if available; then a read-only diff review by an agent that didn't write the change, briefed for security (the diff touches `.github/workflows/`).

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P2 | A consumer calling the workflow with a tag made of ordinary characters sees the same steps, outputs and messages. A tag or draft tag name with a control character now stops in "Resolve draft" instead of continuing. Surfaces read: inputs `tag`, `expected-target-sha`, `asset-filename`; step outputs `tag`, `target_sha` (names unchanged). | none (reusable workflow) | Reverting restores the raw prints; nothing is persisted. | AC 2.3 (existing tests unchanged) plus the new cases |
| P1, P3 | not applicable — touch no persisted state, consumer configuration key, invocation name or artifact path | | | |

## Dependency ordering

P1 → P2 → P3 (P2 and P3 in one dispatch, after P1's result is recorded).

## Risks

- **Over-refusal**: a legitimate tag never contains a control character (git refuses them in ref names), so the validation can't reject a publishable tag. Mitigation: validate control characters only, nothing narrower.
- **`set -euo pipefail` and stderr listings**: the `jq` listings go to stderr; the runner parses workflow commands on stdout — whether it also does on stderr is unestablished, so they're masked regardless.
- **The guard's allow-list becomes the hole.** Mitigation: every entry carries the reason it's constrained; P1's origin table is its source.
- **Security-sensitive path** (`.github/workflows/`): `code-security-reviewer` scopes the surface (P1) and a security-briefed read-only diff review runs before `committed-locally`. The built-in `security-review` isn't used: the session isn't rooted in the worktree.
- **Shared file with #446's F-3?** No: F-3 is `reusable-actionlint.yaml`.

## Open questions

None blocking.

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| the runner parses `##[command]` anywhere in a line that doesn't start with `::`; masking control characters left plain log lines open (BLOCKING) | diff review @ 946e635 | fixed directly, on the operator's decision | actions/runner `ActionCommand.cs` V1 `IndexOf("##[")`, read from source; modelled on the real tf-lint step with `0.55.0##[set-output name=key]attacker`; not measured on a runner | none |
| guard printed step names and paths raw; refusal rule only looked for the word `exit`; `source` binding satisfied by a comment; `x+=`, heredoc into `$GITHUB_OUTPUT`, expansion in the mask's replacement not seen; six surviving mutants | diff review @ 946e635 | fixed directly | crafted files, guard exit 0; mutants passed tests | none |
| `image_name` with a trailing line break refused (unintended behaviour change) | diff review @ 946e635 | fixed directly | `reusable-docker-publish.yaml` exit 1 where f4f1d99 wrote the output | none |
| `readFileSync` stack trace and `JSON.parse` error quote path and content; `refresh_run` raw | diff review @ 946e635 | fixed directly | `reusable-nodejs-coverage.yaml` threshold step; `reusable-release-publish.yml` | none |
| comments claimed more than known (refresh-master "every log line", runner line ends "wasn't measured", hosted images' locale) | diff review @ 946e635 / c81ecd6 | fixed directly | runner `ProcessInvoker.cs` `ReadLine()`; no locale setting found in actions/runner-images | none |
| `scripts/checkout_credentials.py:164` raw annotations, uncaught `yaml.compose` | lane #494 review, moved here as same-pattern sibling | fixed directly | hostile job key produced an extra `::` line | none |
| logged `vbf.json` neutralised values but not keys; two jq listing mutants survived; one message began with a value; guard docstring incomplete | diff review @ c81ecd6 | fixed directly | real step body with `"##[error]from-a-key": 1` | none |
| no blocking findings; remaining non-blocking: forms the leading-value and seam rules don't see (none on the tree), `gh: gh: …` cosmetics in autolabel, `walk` needs jq 1.6 (self-hosted runners with 1.5 unmeasured) | diff review @ 79f7cee | dismissed / stated in the PR's limits | reviewer's probes | none |
| `$GITHUB_STEP_SUMMARY` renders draft title/body and coverage text as markdown | class sweep | to file (needs a decision on fencing/escaping) | publish summary step, refresh-master, nodejs- and python-coverage | to be filed |

## Dispatch log
2026-11-18 P1 dispatched to nolte-engineering:code-security-reviewer — sweep over 28 `reusable-*` workflows and `actions/setup-vale/action.yml`. Predicate: `rg -n '::(error|warning|notice|debug|group|endgroup|add-mask|set-output|save-state|set-env|add-path|stop-commands)\b.*(\$[A-Za-z_{0-9#]|\{[A-Za-z_])'` plus `rg -n '>>\s*"?\$\{?GITHUB_(OUTPUT|ENV|STATE|PATH|STEP_SUMMARY)'` over those files. Counts (workflow commands + `$GITHUB_OUTPUT`, predicate lines only): `reusable-release-publish.yml` raw 10 / constrained 13 / unclear 21; all other files raw 8 / constrained 13 / unclear 13 (release-archive 2/4/9, release-cd-refresh-master 2/1/1, release-drafter 0/0/3, nodejs-coverage 2/0/0, docker-publish 1/0/0, tf-lint 1/0/0).
  Corrections to this artifact's reading, accepted: (1) `$TAG` after `:200` is `unclear`, not raw — it equals a draft tag name by `jq` equality, so it is bounded by whatever GitHub accepts as `tag_name`, which is unestablished; only `:203` carries the raw input. (2) The `target_sha` regex is at `:257`, the write at `:262`. (3) Raw carriers this artifact missed: Python prints `:329`, `:499`, `:503`, `:599` (paths, selector keys and formats from `.github/release-automation.yml`), `:624` (values from repository files), plain prints `:736`/`:753`; `$domain` at `:742` comes from a directory name matched by a glob (`:371-375`), not from `vbf.json` content. (4) `{subject}` at `:637`/`:641` is `unclear` (a lone CR survives `%s`). (5) The sink is any stdout/stderr line, not only lines that start with `::` — the payload brings its own. Whether the runner parses stderr is unestablished; several steps here print `::error::` to stderr on purpose, so stderr is treated as a sink.
  Step-summary hits (weaker sink, markdown only) listed separately: publish `:662-681` (draft title and body), `:757`, `:765`; refresh-master `:261-271`; nodejs-coverage `:75-88`; python-coverage `:79-83`.
2026-11-19 P2+P3 dispatched to nolte-engineering:fullstack-developer — implemented (5d2205e), review fixes c81ecd6 and 79f7cee. Hypothesis confirmed with one limit: the tag prints at the old :197/:203/:209 came before the output write, so the check was moved ahead of them. Refutation accepted: the guard treats `exit 0` as ending the body (the drafter skip).
2026-11-19 verify — `pytest scripts/tests`: 412 passed; guards `workflow_command_masking`, `builtin_action_cache`, `checkout_credentials`: exit 0; `pre-commit run --all-files`: passed; actionlint 1.7.12 run by the specialist: only the two known `job.workflow_*` messages of the older local version. Guard on f4f1d99: 96 hits (plus 5 stale allow-list lines), 0 on HEAD. Rebased onto origin/develop aa561ac. Diff review: security-briefed independent read-only agent, three passes (946e635, c81ecd6, 79f7cee); final head 79f7cee65e3739ecc8755876dbddba13f54604ef, 16 files, 0 blocking.
