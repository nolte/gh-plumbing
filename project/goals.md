# Vision

`gh-plumbing` is the `nolte` portfolio's single source of reusable CI/CD and
repository-governance configuration. It publishes a library of reusable GitHub
Actions workflows, shared `Probot` app configuration commons, and shared
`Renovate` presets. Downstream `nolte/*` repositories consume these **by
reference** (workflow `uses:`, `Probot` `_extends:`, `Renovate` `extends:`).
They get consistent pipelines and governance without duplicating boilerplate.
The repository holds configuration only, with no application code and no running
service.

## Outcomes

- **O-1**: downstream repositories run consistent CI/CD by calling `gh-plumbing`'s
  reusable GitHub Actions workflows at a pinned tag instead of duplicating
  pipeline YAML. _(audience: Downstream repositories consuming reusable workflows)_
- **O-2**: downstream repositories inherit one repository-governance baseline
  (labels, branch protection, housekeeping) by extending `gh-plumbing`'s `Probot`
  configuration commons rather than maintaining per-repository settings.
  _(audience: Downstream repositories extending Probot configurations)_
- **O-3**: downstream repositories keep dependency-update behaviour consistent by
  extending `gh-plumbing`'s shared `Renovate` presets.
  _(audience: Downstream repositories consuming Renovate presets)_
- **O-4**: the maintainer evolves the shared surface with tag-immutable releases
  and green CI, so downstream pins stay stable across changes.
  _(audience: Repository maintainer (nolte))_
