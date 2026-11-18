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
| guard printed job key and values raw: workflow-command injection in its own annotations | diff review @ 742502f | fixed directly | crafted file with job key `"x\n::warning::…"` produced extra `::` lines; after the fix one line | none |
| `uses:` spellings `actions/setup-node/@v6`, `actions//setup-python@v6`, backslash form passed | diff review @ 742502f | fixed directly | guard exit 0 on each; runner splits on `/` and `\` and drops empty segments | none |
| merge key in `with:` hid `cache: pip`; duplicate key: first match won | diff review @ 742502f | fixed directly | guard exit 0 on crafted files | none |
| coverage docs read as unconditional save | diff review @ 742502f | fixed directly | `docs/en/workflows/coverage.md:40` | none |
| YAML error traceback printed a file line raw; non-scalar job key crashed; only the first matched `uses:` applied its rule; surviving mutant | diff review @ 365cb21 | fixed directly | `::warning::via-traceback: [a` appeared on stderr; `TypeError`; exit 0 on setup-python + setup-node; mutant `[:1]` passed 37 tests | none |
| no blocking findings; remaining non-blocking: composite actions outside the two action directories aren't scanned, a `uses:` arriving through a merge key is invisible (both in the docstring), unpinned `pyyaml` in the hook as in the two neighbouring hooks | diff review @ 117c4bc | dismissed (documented boundaries) | — | none |
| `aquasecurity/trivy-action` saves its DB cache through a combined `actions/cache` step, on by default | class sweep | to file (disabling needs the operator's decision) | `action.yaml:102-105`, `:140-147` at ed142fd0; `reusable-trivy.yaml:22` sets no `cache` | to be filed |
| `scripts/checkout_credentials.py:164` prints job and value raw, and its `yaml.compose` is uncaught | diff review @ 742502f / specialist | to file (not in this package's files; class of #492) | pattern read at `:164`; same shape as the reproduced guard finding | to be filed |

## Dispatch log
2026-11-18 P1 dispatched to nolte-engineering:code-security-reviewer — enumerated 31 distinct actions (`rg -n '^\s*(-\s+)?uses:\s*[^./\s]'` over `reusable-*.y*ml` and `actions/**/action.yml`) with every use site, but had no shell and read only three action sources at their pins (setup-python, docker/login-action, chain-bench-action); 25 came back `unclear`. The orchestrator then read `action.yml` / `action.yaml` of all 31 at their pinned SHAs (`gh api repos/<owner>/<repo>/contents/<path>?ref=<sha>`), extracting `runs.using`, `post:`, cache-named inputs and nested `uses:`. Result:
  - **In class: 2.**
    - `actions/setup-node@24997072` — `reusable-nodejs-coverage.yaml:60`; `action.yml:23-25` `package-manager-cache` default true, `:42-43` post `dist/cache-save/index.js`. Fix: `package-manager-cache: false`. In P2.
    - `aquasecurity/trivy-action@ed142fd0` — `reusable-trivy.yaml:22`; `action.yaml:102-105` `cache` default `'true'`, `:140-147` a combined `actions/cache@27d5ce7f` step on `cache-dir` with key `cache-trivy-<date>`, so the save runs in that step's post, after Trivy scanned the consumer's tree and after `upload-sarif` (`reusable-trivy.yaml:48`). The use site sets no `cache` input. No caller-supplied command runs in that job, so the path to rewriting the cached database is Trivy itself or what it reads from the consumer's tree — narrower than the setup-node case. **Not repaired here**: `cache: false` makes every run download the vulnerability database, which changes the workflow's reliability and needs the operator's decision (finding triage condition b). To be filed.
  - **Not in class as used: 29.** `actions/setup-python` (cache only with `cache:`, unset at all 8 sites); `terraform-linters/setup-tflint@6e1e0642` (`action.yml` `cache` default `'false'`, post `dist/post/index.js`; `reusable-tf-lint.yaml:136-139` doesn't set it — a `cache: true` added later would put it in class); `docker/setup-qemu-action@c7c53464` (`cache-image` default true, but `src/main.ts:22-23` pulls with caching inside the main function and the action registers no post callback that saves; the toolkit's `Docker.pull` internals weren't read); `docker/setup-buildx-action@8d2750c6` (`cache-binary` applies only on the download/build path, `src/main.ts:51-56`, inside main; post at `:239-295` only removes the builder); `docker/build-push-action` (`cache-to` is explicit and exported inside the build step); post steps without any cache input: `actions/checkout`, `actions/create-github-app-token`, `docker/login-action`, `github/codeql-action/upload-sarif`; no post step: `actions/stale`, `actions/upload-artifact`, `actions/download-artifact`, `actions/dependency-review-action`, `arduino/setup-task`, `errata-ai/vale-action`, `docker/metadata-action`, `JamesIves/github-pages-deploy-action`, `pascalgn/automerge-action`, `release-drafter/release-drafter`, `actions/cache/restore`, `actions/cache/save`; Docker actions: `chain-bench-action`, `molecule-action`, `hacs/action`, `hadolint-action`, `action-actionlint`, `galaxy-action`; composites without a cache step: `actions/attest-build-provenance`, `home-assistant/actions/hassfest`.
  - Limits: "no cache input in `action.yml`" is the evidence for the post-step-only actions; their sources weren't read. Adjacent, not this class: `docker/build-push-action` with `cache-to: type=gha,mode=max` (`reusable-docker-lint-build.yaml:78`, `reusable-docker-publish.yaml:160`) writes build layers into the GHA cache on purpose.
2026-11-18 P2 dispatched to nolte-engineering:fullstack-developer — implemented (a86a9ba), review fixes 0dac836 and 117c4bc. No refutation; predicate sharpened: any `cache` key on setup-python is a finding, a `uses:` without `@ref` is ignored. The guard is a pre-commit hook as well as a tested script.
2026-11-18 verify — `pytest scripts/tests`: 255 passed; guard: exit 0 on the tree, exit 1 on origin/develop's `reusable-nodejs-coverage.yaml`; `pre-commit run --all-files`: passed; Vale on the changed EN line: no alert; actionlint not installed, not run. Rebased onto origin/develop 4a3ca10 before the final review. Diff review: security-briefed independent read-only agent, three passes (742502f, 365cb21, 117c4bc); final head 117c4bcea76bc0b85c42c69f4b856a71dfc2235c, 8 files, 0 blocking; it confirmed at the pinned source that `package-manager-cache: false` stops restore and save and that an explicit `cache:` would override it.
