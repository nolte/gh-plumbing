---
mission_statement: "gh-plumbing gives downstream nolte/* repositories one centralised, tag-pinned source of reusable GitHub Actions workflows, Probot governance commons, and Renovate presets, so they achieve consistent CI/CD and repository governance without duplicating or copy-pasting pipeline and configuration boilerplate."
relevant_outcomes: [O-1, O-2, O-3, O-4]
audiences:
  - Downstream repositories consuming reusable workflows
  - Downstream repositories extending Probot configurations
  - Downstream repositories consuming Renovate presets
  - Repository maintainer (nolte)
verifies_via: F-1:acceptance-1
time_bound:
  kind: mvp_completion
mvp_status: achieved
created: 2026-07-02
revised_at: null
---

## Statement

`gh-plumbing` gives downstream `nolte/*` repositories one centralised, tag-pinned
source of reusable GitHub Actions workflows, `Probot` governance commons, and
`Renovate` presets. They achieve consistent CI/CD and repository governance
without duplicating or copy-pasting pipeline and configuration boilerplate.

- **Specific**: the statement names *what* (reusable workflows, `Probot` commons,
  and `Renovate` presets, published by reference) and *for whom* (the downstream
  consumer audiences plus the maintainer, resolved in `audiences`).
- **Measurable**: `verifies_via: F-1:acceptance-1`. F-1's acceptance criterion 1
  measures the mission. A downstream repository pins a `reusable-*.yaml` workflow
  at a tag and its pipeline runs green.
- **Achievable**: the minimum viable product is the three already-shipped
  capabilities (`reusable-github-actions-workflows`, `probot-commons-config`,
  `renovate-shared-presets`). Roadmap items R-1 through R-3 carry `mvp: true`,
  `detail: fine`, and `target_sprint: 1`.
- **Relevant**: `relevant_outcomes: [O-1, O-2, O-3, O-4]`. Each entry resolves to
  an outcome in `project/goals.md`.
- **Time-bound**: `time_bound: { kind: mvp_completion }`. The bound is the moment
  the shipped minimum viable product reaches achieved status, not a calendar
  date.

## Audiences

- **Downstream repositories consuming reusable workflows**: the minimum viable
  product delivers a library of `reusable-*.yaml` workflows callable via
  `uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`. A
  consumer gets `pre-commit`, `mkdocs`, `Vale`, `automerge`, release, Docker,
  Ansible, Terraform, `Trivy`, and coverage pipelines without writing its own.
- **Downstream repositories extending Probot configurations**: the minimum viable
  product delivers `.github/commons-*.yml` presets (settings, boring-cyborg,
  release-drafter, stale). A consumer inherits them via `_extends:`, so labels,
  branch protection, and housekeeping stay uniform across the portfolio.
- **Downstream repositories consuming Renovate presets**: the minimum viable
  product delivers `renovate-configs/common`. A consumer extends it via
  `extends: ["github>nolte/gh-plumbing//renovate-configs/common"]`, so
  dependency-update grouping, scheduling, and labelling behave consistently.
- **Repository maintainer (`nolte`)**: the minimum viable product delivers a
  single place to evolve the shared surface. Tag-immutable releases and green CI
  keep downstream pins stable when the surface changes.

## Verification

Feature **F-1: Reusable-workflow adoption** verifies the mission through
acceptance criterion 1: *"A downstream `nolte/*` repository references a
`reusable-*.yaml` workflow at a published tag and its pipeline run completes
green."* This is the `verifies_sprint_value` criterion for sprint 0001. It
already holds across the portfolio, because every `automerge`, docs, and
spelling run in the sibling repositories routes through these workflows. The
mission therefore records the shipped minimum viable product as `achieved`.

## Source

- **Audience artefact**: `AUDIENCES.md` at the `gh-plumbing` repository root,
  consulted at its current develop tip. The four `audiences` entries are the
  primary D1, D2, and D3 direct-consumer audiences plus the maintainer.
- **Outcomes referenced**: O-1, O-2, O-3, O-4 from `project/goals.md`.
- **Authored by**: the `mission-define` cascade (issue nolte/claude-shared#262
  mission-authoring backfill), 2026-07-02. The cascade models the minimum viable
  product retroactively. `gh-plumbing`'s three capabilities already carried
  `status: active` when the repository adopted the planning suite, so the roadmap
  records R-1 through R-3 as `status: done` and opens `mvp_status` at `achieved`
  rather than `defining`.
