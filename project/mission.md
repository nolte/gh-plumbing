---
mission_statement: "gh-plumbing gives downstream nolte/* repositories one centralised, tag-pinned source of reusable GitHub Actions workflows, Probot governance commons, and Renovate presets, so they achieve consistent CI/CD and repository governance without reimplementing or copy-pasting pipeline and configuration boilerplate."
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

gh-plumbing gives downstream `nolte/*` repositories one centralised, tag-pinned
source of reusable GitHub Actions workflows, Probot governance commons, and
Renovate presets, so they achieve consistent CI/CD and repository governance
without reimplementing or copy-pasting pipeline and configuration boilerplate.

- **Specific** — the statement names *what* (reusable workflows + Probot commons
  + Renovate presets, published by reference) and *for whom* (the downstream
  consumer audiences plus the maintainer, resolved in `audiences`).
- **Measurable** — `verifies_via: F-1:acceptance-1`: the mission is measurably met
  when a downstream repository pins a `reusable-*.yaml` at a tag and its pipeline
  runs green (F-1's acceptance criterion 1).
- **Achievable** — the MVP is the three already-shipped capabilities
  (`reusable-github-actions-workflows`, `probot-commons-config`,
  `renovate-shared-presets`); roadmap items R-1..R-3 are `mvp: true`, `detail:
  fine`, `target_sprint: 1`.
- **Relevant** — `relevant_outcomes: [O-1, O-2, O-3, O-4]`, each resolving to an
  outcome in `project/goals.md`.
- **Time-bound** — `time_bound: { kind: mvp_completion }`; the bound is the moment
  the shipped-capability MVP is recorded as achieved, not a calendar date.

## Audiences

- **Downstream repositories consuming reusable workflows** — the MVP delivers a
  library of `reusable-*.yaml` workflows callable via
  `uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`, so a
  consumer gets pre-commit, MkDocs, Vale, automerge, release-drafter/publish,
  Docker, Ansible, Terraform, Trivy, and coverage pipelines without writing its
  own.
- **Downstream repositories extending Probot configurations** — the MVP delivers
  `.github/commons-*.yml` presets (settings, boring-cyborg, release-drafter,
  stale) that a consumer inherits via `_extends:`, so labels, branch protection,
  and housekeeping stay uniform across the portfolio from one source.
- **Downstream repositories consuming Renovate presets** — the MVP delivers
  `renovate-configs/common` that a consumer extends via
  `extends: ["github>nolte/gh-plumbing//renovate-configs/common"]`, so
  dependency-update grouping, scheduling, and labelling behave consistently.
- **Repository maintainer (nolte)** — the MVP delivers a single place to evolve
  the shared surface, with tag-immutable releases and green CI so downstream
  pins remain stable when the surface changes.

## Verification

The mission is verified by feature **F-1 — Reusable-workflow adoption**, acceptance
criterion 1: *"A downstream `nolte/*` repository references a `reusable-*.yaml`
workflow at a published tag and its pipeline run completes green."* This is the
`verifies_sprint_value` criterion for sprint 0001; it already holds across the
portfolio (every automerge/docs/spelling run in the sibling repos routes through
these workflows), so the shipped-capability MVP is recorded as `achieved`.

## Source

- **Audience artefact**: `AUDIENCES.md` at the gh-plumbing repo root (consulted at
  its current develop HEAD); the four `audiences` entries are the primary D1/D2/D3
  direct-consumer audiences plus the maintainer.
- **Outcomes referenced**: O-1, O-2, O-3, O-4 from `project/goals.md`.
- **Authored by**: `mission-define` cascade (issue nolte/claude-shared#262
  mission-authoring backfill), 2026-07-02. The MVP is modelled retroactively —
  gh-plumbing's three capabilities were already `status: active` when the
  planning suite was adopted, so R-1..R-3 are recorded as `status: done` and
  `mvp_status` opens at `achieved` rather than `defining`.
