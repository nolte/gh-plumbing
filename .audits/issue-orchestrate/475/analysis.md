---
artifact-type: issue-orchestration-analysis
repo: nolte/gh-plumbing
issue: "475"
classification: bug
secondary-classes: [infra]
route: direct
status: approved
created: 2026-11-17
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #475 — fix(release-notes): fix PRs that touch docs/ appear twice, and fork PRs land uncategorised
- **URL**: https://github.com/nolte/gh-plumbing/issues/475
- **Labels**: bug
- **Linked items**: #413 (same defect class), #461 (fork PR, uncategorised), #474 (predecessor, merged)
- **Prior art checked**: open PRs — none address #475; partition record `.audits/issue-backlog-partition/2026-11-17.md` (re-checked, not re-derived)

## Classification

- **Primary class**: bug
- **Secondary class(es)**: infra (workflow trigger)
- **Rationale**: published release notes render PRs twice and leave fork PRs uncategorised.
- **Asserted cause verified**:
  - Cause 1 confirmed: `.github/commons-release-drafter.yml:60-66` (Maintenance lists `documentation`); `.github/commons-boring-cyborg.yml:15-19` applies `documentation` by path.
  - Cause 2 confirmed: `.github/workflows/release-drafter.yml:3-7` triggers on `push`/`workflow_dispatch` only; release-drafter v6.4.0 (`index.js:25-32` at 6a93d82) autolabels only on `pull_request[_target].{opened,reopened,synchronize,edited}`.

## Requirements gate

Operator override: the approved partition record plus the issue's own two acceptance criteria (trusted author `nolte`) serve as the requirement; no `requirements-elicit` run.

## Scope

- **In scope**: drop area labels from categories and version-resolver; run the autolabeler on pull requests incl. forks via `pull_request_target` (no checkout, least privilege) as a new opt-in reusable; guard against area labels as category labels; docs.
- **Out of scope**: changing the existing `reusable-release-drafter.yml` permission contract (would break consumers with startup_failure); backfilling labels on already-merged PRs.

## Route

- **Decision**: direct — one outcome, one PR strand, no roadmap item.

## Work packages

### P1 — area label out of categories (cause 1 + class sweep)
- **Acceptance**: no label in `categories[*].labels` or `version-resolver.*.labels` is a key of `labelPRBasedOnFilePath` in `commons-boring-cyborg.yml`.
- **Files**: `.github/commons-release-drafter.yml`
- **Specialist**: no matching specialised agent — generalist remediation (config edit)

### P2 — autolabeler on pull requests (cause 2)
- **Acceptance**: a `pull_request_target` workflow runs release-drafter in autolabel-only mode (`disable-releaser: true`), checks out nothing, grants `pull-requests: write` + `contents: read` only.
- **Files**: `.github/workflows/reusable-release-drafter-autolabel.yml` (new), `.github/workflows/release-drafter-autolabel.yml` (new), docs en/de, README
- **Specialist**: `cicd-pipeline-design` is a skill with its own operator dialogue — not invoked inside a lane; generalist remediation, verified by read-only `nolte-shared:cicd-pipeline-reviewer`.

### P3 — class guard (G1)
- **Acceptance**: pre-commit hook fails when an area label is a release-drafter category/version label.
- **Files**: `.github/scripts/check-release-category-labels.py`, `.pre-commit-config.yaml`
- **Specialist**: no matching specialised agent — generalist remediation

## Dependency order
P1 → P3 (guard asserts P1's repair); P2 independent.
