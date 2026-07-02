---
number: 1
status: closed
started: 2026-07-02
ended: 2026-07-02
value_statement: Downstream nolte/* repositories consume gh-plumbing's reusable workflows, Probot commons, and Renovate presets by reference and get consistent CI/CD and governance without reimplementing boilerplate.
artifact_ref: develop (shipped capabilities, pre-planning-suite)
roadmap_items: [R-1, R-2, R-3]
features: [F-1]
---

## Goal

Downstream `nolte/*` repositories obtain consistent CI/CD and repository
governance from one centralised, tag-pinned source — reusable GitHub Actions
workflows, Probot configuration commons, and Renovate presets — rather than
copy-pasting pipeline and configuration boilerplate. Success is verified by F-1
`acceptance-1`: a downstream repository references a `reusable-*.yaml` workflow
at a published tag and its pipeline run completes green.

## Features

- [F-1](../features/reusable-workflow-adoption.md) — Reusable-workflow adoption — status: done

## Out of scope

- Codifying per-workflow input/secret stability contracts and a deprecation
  policy (tracked as an open question in `AUDIENCES.md`; not part of the shipped
  MVP).
- The repository's own dog-fooding wrapper workflows (`build-static-tests.yaml`,
  `release-cd-refresh-master.yml`, `automerge.yaml`, …), which consume the
  reusable workflows but sit outside the published bounded context.

## Review notes

Retroactive reconciliation (2026-07-02): gh-plumbing's three capabilities
(`reusable-github-actions-workflows`, `probot-commons-config`,
`renovate-shared-presets`) were already `status: active` and consumed
portfolio-wide before this repository adopted the planning suite (issue
nolte/claude-shared#262 mission-authoring backfill). Roadmap items R-1..R-3 and
feature F-1 are therefore recorded as `done`, and this sprint as `closed`, to
document the delivered MVP rather than to plan new work. The value verifier F-1
`acceptance-1` already holds — every automerge/docs/spelling run in the sibling
nolte repositories routes through these reusable workflows.
