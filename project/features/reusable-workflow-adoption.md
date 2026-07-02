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
      evidence: "project/features/ empty (first decomposition); no feature-to-feature overlap possible."
    - kind: prior-art
      target: .github/workflows/reusable-pre-commit.yaml
      resolution: proceed
      evidence: "The reusable-*.yaml workflow library already exists and is consumed portfolio-wide; F-1 documents the shipped adoption contract, it does not build new workflows."
---

## Description

F-1 is the mission-verifying feature for `gh-plumbing`'s shipped minimum viable
product. It captures the adoption contract of the reusable GitHub Actions
workflow library (R-1). A downstream `nolte/*` repository adopts a reusable
workflow by referencing it at a published tag. The contract holds when that
reference resolves and the downstream pipeline runs green. This already holds
across the portfolio, because the `automerge`, docs, and spelling checks in the
sibling repositories all route through
`nolte/gh-plumbing/.github/workflows/reusable-*.yaml@<tag>`. The retroactive
reconciliation therefore records this feature as `done` (issue
nolte/claude-shared#262).

## Acceptance criteria

- [x] **acceptance-1** A downstream `nolte/*` repository references a
  `reusable-*.yaml` workflow at a published tag
  (`uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`) and its
  pipeline run completes green. _(This is the sprint value verifier.)_
- [x] **acceptance-2** Every published `gh-plumbing` tag is a usable pinning
  target. Consumers pin to tags, not to `@develop`.
- [x] **acceptance-3** A breaking change to a reusable workflow's input or secret
  contract ships behind a new tag, so existing downstream pins keep resolving.

## Test hooks

- **acceptance-1**: any sibling repository's Actions run whose job calls a
  `reusable-*.yaml` shows this (for example the `automerge`, docs, and spelling
  checks on `nolte/pre-commit-hooks` and `nolte/kamerplanter-ha`); passing.
- **acceptance-2**: the release-drafter and publish workflow produces tag
  releases, and consumers pin `@<tag>`; passing.
- **acceptance-3**: manual review of the tag and versioning convention; passing.

## Consistency notes

This is a retroactive documentation feature. The underlying capability
(`reusable-github-actions-workflows`) predates the planning suite. This feature
introduces no new implementation. It exists so the mission's
`verifies_via: F-1:acceptance-1` and sprint 1's `value_statement` resolve to a
real acceptance criterion.

## References

- `project/portfolio.yml` capability `reusable-github-actions-workflows`
- `AUDIENCES.md` audience "Downstream repositories consuming reusable workflows"
- `README.md` §Workflows (the published `reusable-*.yaml` catalogue)
