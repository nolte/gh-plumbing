# Vision

gh-plumbing is the nolte portfolio's single source of reusable CI/CD and
repository-governance configuration: a library of reusable GitHub Actions
workflows, shared Probot app configuration commons, and shared Renovate presets
that downstream `nolte/*` repositories consume **by reference** (workflow `uses:`,
Probot `_extends:`, Renovate `extends:`) so they get consistent pipelines and
governance without reimplementing or copy-pasting boilerplate. It is a
configuration-only repository with no application code and no running service.

## Outcomes

- **O-1** — Downstream repositories run consistent CI/CD by calling gh-plumbing's
  reusable GitHub Actions workflows at a pinned tag instead of duplicating
  pipeline YAML. _(audience: Downstream repositories consuming reusable workflows)_
- **O-2** — Downstream repositories inherit one repository-governance baseline
  (labels, branch protection, housekeeping) by extending gh-plumbing's Probot
  configuration commons rather than maintaining per-repo settings.
  _(audience: Downstream repositories extending Probot configurations)_
- **O-3** — Downstream repositories keep dependency-update behaviour consistent by
  extending gh-plumbing's shared Renovate presets.
  _(audience: Downstream repositories consuming Renovate presets)_
- **O-4** — The maintainer evolves the shared surface safely, with tag-immutable
  releases and green CI so downstream pins stay stable across changes.
  _(audience: Repository maintainer (nolte))_
