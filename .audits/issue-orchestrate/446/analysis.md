---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "446"
classification: "feature-request"
secondary-classes: [security]
route: "pipeline (already handed off) — this run implements F-2 inside sprint 0002"
status: approved
created: "2026-11-16"
---

# Issue Orchestration — Pre-analysis (F-2 of #446)

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #446 — Reusable archive-to-release step with provenance, plus a guard against unpinned actions
- **Author trust**: `nolte` (owner) — trusted.
- **Linked items**: #448, #450, #451, #452 (planning, merged). No implementation PR exists (`gh pr list --search 446`).
- **Pipeline state** (established, `project/roadmap.md:77-87`, `project/sprints/0002-verifiable-release-archives.md`): R-4 `active`; sprint 0002 `active`; F-2 `in_progress`; F-3..F-6 `ready`.
- **Requirements**: `project/requirements/release-archive-provenance.md`, `U_gate = 0.85 ≥ τ_high = 0.8` → gate satisfied. Scope of this run: Strand A (R1–R4e, AC1) = feature F-2.

## Classification

- **Primary class**: feature-request (new reusable workflow).
- **Secondary**: security (supply-chain provenance; new `id-token`/`attestations` scopes; workflow files are security-sensitive paths).
- **Asserted cause verified**: the issue asserts the HACS path is the only pre-publish asset builder — confirmed: `.github/workflows/reusable-release-publish.yml:601-671` (HACS-only, `if: steps.vbf.outputs.source == 'hacs'`); no `reusable-release-archive.yml` exists (`ls .github/workflows`). No workflow in the repo installs Task today (`grep arduino/setup-task|go-task .github/workflows` empty).

## Route

- **Decision**: pipeline (issue level, done earlier) → this run implements one feature, F-2, as a single PR strand. F-3..F-6 stay with sprint 0002 and are not touched.

## Scope

- **In scope**: new `reusable-release-archive.yml`; a self-test workflow with throwaway drafts plus a fixture Task target (operator decision 2026-11-16); EN+DE docs page and nav entry; F-2 feature-file test-hook updates once verified.
- **Out of scope**: any change to `reusable-release-publish.yml` (R2); zizmor/pinning check (F-3); spec edits in claude-shared (F-4, F-6); vale-style migration (F-5).

## Work packages

### P1 — `reusable-release-archive.yml`

- **Problem**: no reusable builds an arbitrary Task-built archive, attests it, and attaches it to the draft before publish.
- **Design (from R1–R4e, prior art)**: `workflow_call` inputs `tag` (optional; single-draft resolution copied from `reusable-release-publish.yml:147-208`, incl. reachability check), `task-target` (required), `assets` (newline-separated paths/globs, required), `dry-run` (bool). Secret `token`. Steps: resolve draft (fail if tag names a published release or no draft — R4e, before any write) → checkout at target SHA → install Task (digest-pinned action, non-interactive; Taskfiles with remote includes need `task --yes`) → `task <target>` → expand globs, fail if any pattern matches nothing (R4a) → `actions/attest-build-provenance` (digest-pinned, same pin as `reusable-docker-publish.yaml:181`) over all subjects (R4c: attest before upload; failure stops the job) → unless dry-run, `gh release upload <tag> <files> --clobber` (R4b/R4d). Job permissions: `contents: write`, `id-token: write`, `attestations: write` at job level only, with the caller warning comment from `reusable-docker-publish.yaml:68-79` (R3). Never call `gh release edit` / never touch body, name, draft, prerelease (acceptance-7). Outputs: resolved `tag`, uploaded asset list.
- **Acceptance**: F-2 acceptance-1..5, -7.
- **Files**: `.github/workflows/reusable-release-archive.yml`
- **Specialist**: `nolte-shared:cicd-pipeline-design` (skill; designs and writes GitHub Actions workflows against github-actions-best-practices / continuous-delivery).
- **Depends on**: none

### P2 — Self-test workflow and fixture target

- **Problem**: the test hooks need live runs without touching the real release-drafter draft.
- **Design**: `.github/workflows/test-release-archive.yml`, triggers `workflow_dispatch` and `pull_request` (paths: the reusable, the test workflow, `Taskfile.yml`; same-repo PRs only, since fork tokens are read-only). Setup job creates a throwaway draft (`gh release create test-archive-<run_id>-<attempt> --draft --target <develop SHA>`; draft releases create no tag). Jobs: positive call; re-run call against the same draft (content differs per call → replacement verified); dry-run call; negative calls with `continue-on-error`-free `needs` + `if: always()` verifier asserting `result == 'failure'` for (a) empty glob and (b) the latest published gh-plumbing tag (R4e; verifier compares `gh release view --json body,name,isDraft,isPrerelease,assets` before/after). Verifier runs `gh attestation verify` per asset and the body/name/flags-unchanged check on the throwaway draft. Cleanup job (`if: always()`) deletes the throwaway draft. Fixture: local task `release-archive:fixture` in `Taskfile.yml` writing `build/fixture-*.zip` with run-specific content.
- **Acceptance**: the test workflow is green on the PR and exercises acceptance-1,-2(a,c),-3,-4,-7.
- **Files**: `.github/workflows/test-release-archive.yml`, `Taskfile.yml`, `.gitignore` (`build/` if missing)
- **Specialist**: `nolte-shared:cicd-pipeline-design`
- **Depends on**: P1

### P3 — Consumer documentation

- **Problem**: acceptance-6 requires a page stating the caller grants `id-token: write` + `attestations: write` (and `contents: write`), else `startup_failure`.
- **Files**: `docs/en/workflows/release-archive.md`, `docs/de/workflows/release-archive.md`, `mkdocs.yml` nav, `docs/*/workflows/index.md` / `release.md` cross-links.
- **Specialist**: no matching specialised agent — generalist remediation (`nolte-shared:audience-doc-author` exists but requires an `audience-identify` artifact, which this repo doesn't have). Pattern: `docs/en/workflows/container.md`. Prose verified by `nolte-shared:prose-vale-curator` (`vale --minAlertLevel=suggestion` on added lines, <10 alerts; `docs/de/**` exempt).
- **Depends on**: P1 (inputs final)

### P4 — Verify and record

- `nolte-shared:cicd-pipeline-reviewer` (read-only) over P1+P2; built-in `security-review` from the worktree; `actionlint`/pre-commit; `mkdocs build --strict`; PR checks incl. the new self-test green.
- Update `project/features/reusable-release-archive.md`: tick verified criteria, set hooks `passing`/`skipped` and normalise them to the spec format `- **acceptance-<n>** — <mechanism> — <status>` (`spec/project/feature/en.md:57`). Then `sprint-execute` op 3 (`in_progress → done`) — only if every hook is resolved.
- **Depends on**: P1–P3

## Dependency ordering

P1 → P2 → P3 → P4

## Risks

- **Attestation-failure path (acceptance-2b)** can't be forced without a test-only input on a public API. Proposal: hook `skipped` with rationale (attest step precedes upload under `set -e`/step failure semantics; reviewed in P4). Operator decision needed.
- **R4e test against a real published release**: if the guard were wrong, an asset would land on a public release. Mitigation: guard sits in the resolve step before any write; the verifier compares the release's asset list before/after; P4 review precedes the first run.
- **Self-test creates attestations** in gh-plumbing for fixture files — harmless records, named `fixture-*`.
- **Two copies of draft resolution** (R2, accepted in F-2 Risks).
- Workflow-file changes propagate to every consumer only once they call the new reusable; existing callers are unaffected (acceptance-5).

## Open questions

Resolved by the operator on 2026-11-16 (decomposition approved):
1. acceptance-2b → hook `skipped` with rationale (attest precedes upload; verified by review in P4). No test-only input.
2. R4e negative test runs against the latest published gh-plumbing release, with before/after comparison.

## Deviations approved during P1/P2 (operator, 2026-11-16)

1. The reusable splits into `resolve` → `build` (contents: read, no OIDC; runs the consumer's Task target) → `attest-attach` (contents/id-token/attestations write). The consumer's build code never holds a write scope or an OIDC token.
2. No reachability check of the draft target from `develop` in the archive reusable; `reusable-release-publish.yml` keeps that gate for the publish. This lets the PR self-test build at the PR head, where the fixture target exists.
3. Negative scenarios (acceptance-2a empty glob, 2c published release) are `workflow_dispatch`-only (`scenario` input) because a failing reusable-call job turns the whole run red and `uses:` jobs don't support `continue-on-error`. They can run only once the workflow is on `develop`; their run is red by design and the `verify` job carries the outcome. F-2 `done` therefore follows the merge plus both dispatch runs.

## Findings

- Docs-specialist precondition gap: no audience artifact in gh-plumbing.
