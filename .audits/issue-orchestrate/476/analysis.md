---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "476"
classification: "security"
secondary-classes: ["bug"]
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #476 — tf-lint cache key uses the runner label and saves after plugin code ran
- **URL**: https://github.com/nolte/gh-plumbing/issues/476
- **Labels**: cicd, security
- **Linked items**: #468, #472 / PR #477 (merged; fixed the same class in `reusable-pre-commit.yaml` only — files: `reusable-pre-commit.yaml`, `docs/{en,de}/workflows/static-tests.md`). No open PR references #476.
- **Prior art checked**: hand-off record from `issue-backlog-partition` run 2026-11-18-gh-plumbing, re-checked against the live issue (open, author `nolte`, 0 comments). No roadmap item or feature covers it.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/476-tf-lint-cache`, branch `fix/476-tf-lint-cache` off `origin/develop` @ 1c33b7b; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Lane**: `lane: true` — returns `committed-locally`.
- **Gates**: scope, requirements override (issue text states defect, fix and acceptance), route and decomposition approved under the operator's standing authorisation of 2026-11-18 ("arbeite möglichst autonom"), recorded in `.resume/issue-backlog-partition/2026-11-18-gh-plumbing.yml`.

## Classification

- **Primary class**: security
- **Secondary class(es)**: bug (stale binaries after a runner image change)
- **Rationale**: a cache written after third-party plugin code ran, into the default-branch scope every branch restores from.
- **Asserted cause verified**: confirmed: `.github/workflows/reusable-tf-lint.yaml:44-52` is one combined `actions/cache@0057852… # v4.3.0` step on `~/.tflint.d/plugins`, key `${{ matrix.os }}-tflint-${{ inputs.tflint_version }}-${{ hashFiles(inputs.config_path) }}`, no event condition; `matrix.os` is `[ubuntu-latest, macos-latest, windows-latest]` (`:36`). The combined action's post step saves at job end, after `tflint -f compact` (`:69`). The issue's `:42-50` is off by two lines.

## Scope

- **In scope**: split the cache step into restore and save (same pinned SHA); save only for `pull_request` events, only on a miss, after `tflint --init` and before `tflint -f compact`; put the runner OS release into the key on all three matrix systems; a guard that refuses a combined `actions/cache` step in this repository's workflows; the README row or comment text only where it now says something false.
- **Out of scope**: running tflint isolated from the runner context (the residual risk `reusable-pre-commit.yaml:196-200` names for the same pattern); changing tflint or plugin versions.

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Split the tflint plugin cache and key it on the OS release

- **Problem statement**: one combined cache step saves after plugin code ran, on every event, keyed on the runner label.
- **Acceptance criteria**:
  1. The workflow has an `actions/cache/restore` step before `Setup TFLint`/`Init TFLint` and an `actions/cache/save` step, both pinned to `0057852bfaa89a56745cba8c7296529d2fc39830`; no combined `actions/cache` step remains.
  2. The save step's condition is `github.event_name == 'pull_request'` and a cache miss; it sits after `tflint --init` and before `tflint -f compact`. A default-branch run, a push to any branch, merge-queue and `pull_request_target` runs never save.
  3. The key carries the runner's OS release, computed in a step that works on Linux, macOS and Windows runners, with a stated fallback where the source is missing (for example a self-hosted runner), plus the existing tflint version and config hash. The comment says which source it uses and what it changes on.
  4. The key gets a new prefix or shape so no entry saved by the old combined step is ever restored again.
  5. Comments explain the save policy and its cost the way `reusable-pre-commit.yaml:174-201` does, without copying text that isn't true for tflint.
  6. `actionlint` (CI flags) passes on the file.
- **Touched files / artifacts**: `.github/workflows/reusable-tf-lint.yaml`; `README.md:46` only if needed.
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: none

### P2 — Guard: no combined `actions/cache` step in this repository's workflows

- **Problem statement**: the class was found twice by sweep (#468/#472, then #476); nothing refuses a third occurrence.
- **Acceptance criteria**:
  1. A check that runs in the existing static gate (pre-commit, which `static / Static CI Tests` runs) fails on `uses: actions/cache@…` in `.github/workflows/*.y{a}ml` and passes on `actions/cache/restore@` and `actions/cache/save@`.
  2. It fails against `origin/develop`'s `reusable-tf-lint.yaml` and passes on the fixed tree (both runs shown).
  3. Its message names the rule and points at the reason (#472/#476).
  4. Smallest form that fits the repository: a `pygrep` hook in `.pre-commit-config.yaml` if that is enough; a script under `scripts/` with a test only if the existing guards' pattern (`scripts/checkout_credentials.py`) demands it — say which and why.
- **Touched files / artifacts**: `.pre-commit-config.yaml` (or `scripts/` + `scripts/tests/` + `build-static-tests.yaml`)
- **Specialist**: `nolte-engineering:fullstack-developer`
- **Depends on**: P1 (the guard must pass on the fixed tree)

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P1 | consumers take one cold plugin cache; afterwards default-branch runs and the first run of each pull request install plugins cold, later runs of the same pull request restore | none (reusable workflow); surfaces read: the Actions cache entries under the old key | a revert restores the combined step and the old key; entries a poisoned run already saved under the old key would be restored again | key prefix differs from the old shape (AC 4) |
| P2 | not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path | | | |

Inputs and secrets of the reusable are unchanged.

## Dependency ordering

P1 → P2.

## Risks

- No workflow in this repository calls `reusable-tf-lint.yaml`, so no CI run exercises the change before a consumer does. Mitigation: `actionlint`, the reference pattern already live in `reusable-pre-commit.yaml`, and the limit stated in the PR.
- The OS-release source differs per platform and may be absent on self-hosted runners. Mitigation: AC 3 requires a fallback that still yields a usable key.
- Security-sensitive path (`.github/workflows/`): a security-briefed read-only diff review runs before the lane returns. The whole-codebase `code-security-reviewer` audit isn't run for a one-step change; the review brief covers cache scope, event conditions and untrusted input.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|

## Dispatch log
