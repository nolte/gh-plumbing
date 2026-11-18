---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "494"
classification: "security"
secondary-classes: []
route: "direct"
status: approved
created: "2026-11-18"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #494 — Check whether actions/setup-node's built-in cache is the same class as #472/#476
- **URL**: https://github.com/nolte/gh-plumbing/issues/494
- **Labels**: cicd, security
- **Linked items**: #472 / PR #477 and #476 / PR #493 (both merged; the class fixed for explicit `actions/cache` steps; #493's diff review found this). `closedByPullRequestsReferences` is empty; no open PR; no comments.
- **Prior art checked**: guard `no-combined-actions-cache` at `.pre-commit-config.yaml:33-37` (matches `uses: actions/cache@` only); step-pairing guard `scripts/checkout_credentials.py` with `scripts/tests/test_checkout_credentials.py`, run by `build-static-tests.yaml:144-146`; reference split pattern in `reusable-pre-commit.yaml` and `reusable-tf-lint.yaml`.
- **Working copy**: `~/repos/.worktrees/gh-plumbing/494-setup-node-builtin-cache`, branch `fix/494-setup-node-builtin-cache` off `origin/develop` @ f4f1d99; detect=200; created via fallback `git worktree add -b`; ignore check `git check-ignore -q` on this path: ignored=1
- **Caller**: `issue-backlog-partition` run `2026-11-18-2-gh-plumbing`, `lane: true` → ends at `committed-locally`. Develop-health re-read 2026-11-18T22:15Z: red only 25970095265 and 30715245456, both overridden by the operator in the caller's checkpoint.

## Classification

- **Primary class**: security (confirmed by the operator, 2026-11-18)
- **Secondary class(es)**: none
- **Rationale**: a cache saved after third-party code ran, into the default-branch scope on a default-branch run.
- **Asserted cause verified** — the issue marks its own cause "not established"; this run settled it:
  - *Does the pinned `actions/setup-node` cache without an explicit `cache:` input?* — **confirmed, conditionally.** `action.yml` at 249970729cb0ef3589644e2896645e5dc5ba9c38 (v6.5.0): input `package-manager-cache`, `default: true`, described as "By default, caching is enabled when either devEngines.packageManager or the top-level packageManager field in package.json specifies npm as the package manager." `src/main.ts:24-26` reads it defaulting to true; `:78-86` restores the cache when `getNameFromPackageManagerField()` returns `npm` (`:149-162`). So it caches when the consumer's `package.json` names npm there, and not otherwise.
  - *When does it save?* — **confirmed**: `action.yml:39-43`, `post: 'dist/cache-save/index.js'`, `post-if: success()`. A post step runs after the job's steps, so after `inputs.install-command` (`reusable-nodejs-coverage.yaml:64-65`) and `inputs.test-command` (`:67-68`). *What paths the post step saves* is unestablished (the cache-save source wasn't read); the observation that would settle it is reading `src/cache-save.ts` at the pin. The fix doesn't depend on it.
  - *The workflow sets neither input* — confirmed: `reusable-nodejs-coverage.yaml:60-62` passes only `node-version`.
  - *`actions/setup-python`* (8 steps, v6.3.0 @ ece7cb06…) — confirmed not in the class as used: `action.yml:10-12` has `cache` with no default and no `package-manager-cache`-style input; `grep -nE -A6 'uses:\s*actions/setup-(python|node)@' … | grep cache` returns nothing, so no step passes `cache:`. It has the same post step (`:46-47`), so a `cache:` input added later would put it in the class.
  - *Other actions with a cache of their own* — unestablished for the rest of the 31 distinct actions the reusable workflows use (candidates by name: `aquasecurity/trivy-action`, `docker/build-push-action`, `docker/setup-buildx-action`, `terraform-linters/setup-tflint`, `arduino/setup-task`, `reviewdog/action-actionlint`, `errata-ai/vale-action`, `hadolint/hadolint-action`). P1 settles it.

## Scope

- **In scope**: disable the built-in cache at the `setup-node` step; a guard that refuses the class for `setup-node` and `setup-python`; a recorded sweep over every action the reusable workflows and composite actions use, with the hit count; the consumer-facing note in `docs/{en,de}/workflows/coverage.md` if the behaviour change is visible there.
- **Out of scope**: rebuilding an npm cache with split restore/save (the operator chose to disable); repairing sweep hits in other actions beyond finding triage (a)–(c) — anything needing a decision is filed.

## Requirements gate

No artefact under `project/requirements/` covers #494. **Operator override, 2026-11-18:** `requirements-elicit` skipped; the issue's to-do list is its acceptance, and the operator chose the fix variant (disable plus guard).

## Route

- **Decision**: direct
- **Rationale**: one coherent outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Sweep: which actions used here save a cache in a post step by default (audit, read-only)

- **Problem statement**: the class is "a cache saved after third-party code ran, without the workflow asking for it". Two actions are settled above; the rest of the list isn't.
- **Acceptance criteria**: for every distinct `uses:` action in `.github/workflows/reusable-*.y*ml` and `actions/**/action.yml`, at its pinned ref: does its `action.yml` declare a `post:` step or a composite `actions/cache` step, is caching on by default or only by input, and does any step here turn it on. A table with `file:line` of each use, the pin, the verdict (`in class` / `not in class as used` / `unclear` with what would settle it), and the evidence (the `action.yml` lines read at the pin). The enumerating command stated. A hit count.
- **Touched files / artifacts**: none (read-only).
- **Specialist**: `nolte-engineering:code-security-reviewer`, scoped to this class and these paths (step one of the audit → fix → verify chain).
- **Depends on**: none

### P2 — Disable the built-in cache and guard the class

- **Problem statement**: hypothesis — `package-manager-cache: false` on the `setup-node` step removes the save; a guard that pairs each `setup-node` / `setup-python` step with its `with:` keys keeps it removed.
- **Acceptance criteria**:
  1. `reusable-nodejs-coverage.yaml`'s `setup-node` step sets `package-manager-cache: false`, with a comment saying why (the post-step save after the caller's commands) and naming #494.
  2. A guard, following `scripts/checkout_credentials.py` (YAML-node based, selector is the step's `uses:` value, covers `.github/workflows/`, `.github/actions/` and `actions/`): refuses an `actions/setup-node@` step that doesn't set `package-manager-cache: false` or that sets `cache:`; refuses an `actions/setup-python@` step that sets `cache:`. Wired as a pre-commit hook beside `no-combined-actions-cache` and tested in `scripts/tests/` with the test file named in `build-static-tests.yaml`'s `pytest-args`.
  3. The guard fails on the pre-fix workflow (shown against `git show origin/develop:.github/workflows/reusable-nodejs-coverage.yaml`) and passes on the tree after the fix; it reports nothing on the eight `setup-python` steps.
  4. `pytest scripts/tests` and `pre-commit run --all-files` pass.
  5. `docs/en/workflows/coverage.md` and `docs/de/workflows/coverage.md` say, in one or two sentences, that the workflow doesn't cache npm's store and why — only if the pages describe the workflow's behaviour at that level; if they only embed the file, no prose change.
  6. Every P1 hit other than `setup-node` is either repaired here under finding triage (a)–(c) and covered by the guard, or listed for filing with its evidence.
- **Touched files / artifacts**: `.github/workflows/reusable-nodejs-coverage.yaml`, `scripts/<guard>.py`, `scripts/tests/test_<guard>.py`, `.pre-commit-config.yaml`, `.github/workflows/build-static-tests.yaml`, possibly `docs/{en,de}/workflows/coverage.md`.
- **Specialist**: `nolte-engineering:fullstack-developer` (workflow YAML plus a Python guard and its tests; no candidate names guard-script authoring).
- **Depends on**: P1

### Verify (operation 6, not a package)

`pytest scripts/tests`, `pre-commit run --all-files`; then a read-only diff review by an agent that didn't write the change, briefed for security (the diff touches `.github/workflows/`).

## Existing installations / upgrade / rollback

Health gate: none (reusable workflow consumed by ref).

| Package | Upgraded state | Update health gate | What a rollback restores and what it can't | Proving check |
|---|---|---|---|---|
| P2 | A consumer whose `package.json` names npm as `packageManager` loses the implicit npm cache: installs get slower, nothing else changes. Every other consumer sees no change. Surfaces read: none of the workflow's inputs or outputs change. An existing poisoned or stale cache entry is no longer restored, because `setup-node` no longer restores at all. | none (reusable workflow) | Reverting restores the implicit cache. It can't remove cache entries already saved in consumers' repositories; those expire on GitHub's schedule or are deleted by hand. | AC 2.1, 2.3 |
| P1 | not applicable — touches no persisted state, consumer configuration key, invocation name or artifact path | | | |

## Dependency ordering

P1 → P2.

## Risks

- **Slower installs for consumers that got the cache implicitly.** Accepted by the operator's choice of variant; stated in the PR's rollout notes.
- **The guard's selector is two action names**, so a third action with the same behaviour isn't refused. Mitigation: P1 enumerates all actions used today; the guard's docstring says what it doesn't cover; a hit in another action extends the guard or is filed.
- **Security-sensitive path** (`.github/workflows/`): `code-security-reviewer` scopes the surface (P1) and a security-briefed read-only diff review runs before `committed-locally`. The built-in `security-review` isn't used: the session isn't rooted in the worktree.
- **`.pre-commit-config.yaml` and `build-static-tests.yaml` are also touched by lane #492** (a new test file in `pytest-args`, possibly). The two lanes' pull requests go through the serial train, so the second rebases onto the first; the overlap is one line each.

## Open questions

None blocking.

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|

## Dispatch log
