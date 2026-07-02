---
number: 1
status: closed
started: 2026-07-02
ended: 2026-07-02
value_statement: Downstream nolte/* repositories consume gh-plumbing's reusable workflows, Probot commons, and Renovate presets by reference and get consistent CI/CD and governance without duplicating boilerplate.
artifact_ref: develop (shipped capabilities, pre-planning-suite)
roadmap_items: [R-1, R-2, R-3]
features: [F-1]
---

## Goal

Downstream `nolte/*` repositories obtain consistent CI/CD and repository
governance from one centralised, tag-pinned source. That source covers reusable
GitHub Actions workflows, `Probot` configuration commons, and `Renovate` presets.
The consumer no longer copy-pastes pipeline and configuration boilerplate. F-1
`acceptance-1` verifies success: a downstream repository references a
`reusable-*.yaml` workflow at a published tag and its pipeline run completes
green.

## Features

- [F-1](../features/reusable-workflow-adoption.md): Reusable-workflow adoption, status: done

## Out of scope

- Codifying per-workflow input and secret stability contracts and a deprecation
  policy. `AUDIENCES.md` tracks this as an open question, outside the shipped
  scope.
- The repository's own dog-fooding wrapper workflows (`build-static-tests.yaml`,
  `release-cd-refresh-master.yml`, `automerge.yaml`, and the like). They consume
  the reusable workflows but sit outside the published bounded context.

## Review notes

Retroactive reconciliation (2026-07-02): `gh-plumbing`'s three capabilities
(`reusable-github-actions-workflows`, `probot-commons-config`,
`renovate-shared-presets`) already carried `status: active` and served the
portfolio before this repository adopted the planning suite (issue
nolte/claude-shared#262 mission-authoring backfill). This sprint therefore
records roadmap items R-1 through R-3 and feature F-1 as `done`, and itself as
`closed`. That documents the delivered minimum viable product rather than new
planned work. The value verifier F-1 `acceptance-1` already holds: every `automerge`,
docs, and spelling run in the sibling `nolte` repositories routes through these
reusable workflows.
