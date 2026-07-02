---
id: F-1
title: Reusable-workflow adoption
status: done
roadmap_item: R-1
sprint: 1
created: 2026-07-02
ended: 2026-07-02
verifies_sprint_value: acceptance-1
consistency_check:
  performed_at: 2026-07-02
  agent_version: manual-fallback (retroactive; feature-consistency-reviewer not run cross-repo)
  findings:
    - kind: clean
      target: project/features/
      resolution: proceed
      evidence: "project/features/ empty (first decomposition) — no feature-to-feature overlap possible."
    - kind: prior-art
      target: .github/workflows/reusable-pre-commit.yaml
      resolution: proceed
      evidence: "The reusable-*.yaml workflow library already exists and is consumed portfolio-wide; F-1 documents the shipped adoption contract, it does not build new workflows."
---

## Description

F-1 is the mission-verifying feature for gh-plumbing's shipped MVP: it captures
the adoption contract of the reusable GitHub Actions workflow library (R-1). A
downstream `nolte/*` repository adopts a reusable workflow by referencing it at a
published tag; the contract is met when that reference resolves and the
downstream pipeline runs green. This already holds across the portfolio — the
automerge, docs, and spelling checks in the sibling repositories all route
through `nolte/gh-plumbing/.github/workflows/reusable-*.yaml@<tag>` — so the
feature is recorded `done` as part of the retroactive MVP reconciliation
(issue nolte/claude-shared#262).

## Acceptance criteria

- [x] **acceptance-1** A downstream `nolte/*` repository references a
  `reusable-*.yaml` workflow at a published tag (`uses:
  nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`) and its
  pipeline run completes green. _(This is the sprint value verifier.)_
- [x] **acceptance-2** Every published gh-plumbing tag is a usable pinning target
  (consumers pin to tags, not to `@develop`).
- [x] **acceptance-3** A breaking change to a reusable workflow's input or secret
  contract ships behind a new tag, so existing downstream pins keep resolving.

## Test hooks

- **acceptance-1** — observable in any sibling repo's Actions run whose job calls
  a `reusable-*.yaml` (e.g. the automerge / docs / spelling checks on
  nolte/pre-commit-hooks, nolte/kamerplanter-ha) — passing.
- **acceptance-2** — release-drafter/publish workflow produces tag releases;
  consumers pin `@<tag>` — passing.
- **acceptance-3** — manual review of the tag/versioning convention — passing.

## Consistency notes

Retroactive documentation feature: the underlying capability
(`reusable-github-actions-workflows`) predates the planning suite. No new
implementation is introduced; the feature exists so the mission's `verifies_via:
F-1:acceptance-1` and sprint 1's `value_statement` resolve to a real acceptance
criterion.

## References

- `project/portfolio.yml` capability `reusable-github-actions-workflows`
- `AUDIENCES.md` audience "Downstream repositories consuming reusable workflows"
- `README.md` §Workflows (the published reusable-*.yaml catalogue)
