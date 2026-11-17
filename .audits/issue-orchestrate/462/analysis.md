---
artifact-type: issue-orchestration-analysis
repo: nolte/gh-plumbing
issue: "462"
classification: bug
secondary-classes: [infra]
route: direct
status: approved
created: 2026-11-17
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #462 — Fork pull requests can never satisfy the required checks from Static CI Tests
- **URL**: https://github.com/nolte/gh-plumbing/issues/462
- **Labels**: bug, cicd
- **Author**: `nolte` (repository owner, trusted)
- **Linked items**: #461 (fork PR, helper branch `ci/pr-461-checks`); no closing PR (`closedByPullRequestsReferences: []`)
- **Prior art checked**: `gh pr list --search 462` → none; no `project/requirements/` artefact for this issue

## Requirements gate

- **Override (operator, 2026-11-17)**: `requirements-elicit` skipped. The trusted author states the proposed change, its constraints (no `pull_request_target`) and the verification. Operator confirmed the override.

## Classification

- **Primary class**: bug
- **Secondary class(es)**: infra
- **Rationale**: a required-check producer that can't run for one class of pull request is a defect in the CI wiring, not a feature.
- **Asserted cause verified**: confirmed.
  - `.github/workflows/build-static-tests.yaml:3-5` has only `push:` and `workflow_dispatch:`.
  - `.github/settings.yml:73-75` lists the three contexts it produces as required.
  - `gh run list --workflow build-static-tests.yaml` shows a `push` run on `ci/pr-461-checks`, the helper-branch workaround.

## Scope

- **In scope**
  - Add a `pull_request` trigger to `build-static-tests.yaml`. Narrow `push` to `develop` and `master` (operator decision).
  - In `reusable-trivy.yaml`, skip the SARIF upload when the pull request head comes from a fork (operator decision: in the reusable, so consumers inherit it).
  - Update the trigger snippet and description in `docs/{en,de}/workflows/static-tests.md`.
- **Out of scope**
  - `pull_request_target`, which the issue forbids.
  - Changing the required-context list.
  - Rolling out to other consumer repositories.

## Fork-token scope survey (established)

| Job | Scopes | Fork-safe |
|---|---|---|
| actionlint | `contents: read`; annotations, no `checks: write` (`reusable-actionlint.yaml:40-62`) | yes |
| static | `contents: read`; Docker Hub login is `continue-on-error` (`reusable-pre-commit.yaml:115`) | yes |
| docs | `contents: read` (`reusable-mkdocs-build.yaml:38`) | yes |
| security | `security-events: write`, `actions: read` (`reusable-trivy.yaml:9-12`) | **no**: the upload fails on a read-capped token |
| *-tests, docs-freshness | `contents: read` | yes |
| chain-bench | `contents: read`, token passed as a secret (`reusable-chain-bench.yaml:17,29`) | yes (GITHUB_TOKEN is available, read-only) |

## Route

- **Decision**: direct
- **Rationale**: one outcome, one PR strand, no roadmap item.

## Work packages

### P1 — Workflow triggers and fork-safe SARIF upload

- **Problem statement**: Fork pull requests never trigger `build-static-tests.yaml`. Its `security` job's SARIF upload needs a write scope that a fork's token doesn't get.
- **Acceptance criteria**
  - `on:` contains `pull_request:`, `push:` with `branches: [develop, master]`, and `workflow_dispatch:`.
  - The upload step in `reusable-trivy.yaml` carries an `if:` that is false exactly when `github.event.pull_request.head.repo.full_name != github.repository`, and true for push events.
  - Comments explain both choices and that `pull_request_target` is deliberately not used.
  - The concurrency comment covers `refs/pull/N/merge`.
  - actionlint and pre-commit pass.
- **Touched files**: `.github/workflows/build-static-tests.yaml`, `.github/workflows/reusable-trivy.yaml`
- **Specialist**: `nolte-engineering:fullstack-developer` (agent).
  - Considered and rejected: `nolte-shared:cicd-pipeline-design`. It is a whole-pipeline design/audit skill with operator dialogues, not a bounded two-file patch.
- **Depends on**: none

### P2 — Trigger documentation

- **Problem statement**: `docs/{en,de}/workflows/static-tests.md` say the bundle runs "on every push" and show a `push:`-only consumer snippet. Consumers who copy it inherit the fork defect.
- **Acceptance criteria**
  - EN and DE in parity.
  - The snippet shows `pull_request` plus `push` on the default branch.
  - A short note explains why fork PRs need `pull_request`, and that `pull_request_target` is not an alternative.
  - Vale: fewer than 10 annotations on added lines.
  - `mkdocs build --strict` stays green.
- **Touched files**: `docs/en/workflows/static-tests.md`, `docs/de/workflows/static-tests.md`
- **Specialist**: `nolte-shared:audience-doc-author` (agent; audience artefact `AUDIENCES.md`)
- **Depends on**: P1 (documents its final shape)

## Dependency ordering

P1 → P2 → verify (`nolte-shared:cicd-pipeline-reviewer` on the diff; pre-commit/actionlint)

## Risks

- **Unestablished: `startup_failure` for fork PRs.** A fork PR whose workflow declares `security-events: write` might be refused with `startup_failure` rather than get a downgraded token.
  - GitHub documents fork tokens as read-capped; the caller here grants what the callee asks, so the startup_failure pattern from #422 doesn't apply structurally.
  - Settling observation: a real fork PR after merge. Not made.
- **Same-repository PRs now get their checks from `pull_request` instead of `push`.** Context names don't change (`<job> / <name>`).
  - Feature-branch pushes without an open PR no longer run the bundle.
- **Concurrency**: `github.ref` for PRs is `refs/pull/N/merge`, so each PR gets its own group, separate from develop pushes. Behaviour is intended.
- **Consumer impact (public API)**: the `reusable-trivy.yaml` change only skips a step for fork PRs, so it is backwards compatible.

## Open questions

none

## Findings

- The trigger shape can't be measured pre-merge for the fork case. Verification of acceptance criterion 4 of the issue (a real fork PR showing all four contexts) moves to the post-merge note in the PR risk section.
