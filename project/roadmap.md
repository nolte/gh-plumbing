# Roadmap

This file is the work queue governed by `spec/project/roadmap/`. Each entry is a
level-3 heading followed by a `yaml` code block (`id`, `title`, `detail`,
`outcomes`, `target_sprint`, `mvp`, `status`, in that order) and a free-text
body. Detail level (`detail`: `fine` / `coarse` / `backlog`) and the status
lifecycle (`status`: `proposed`, `active`, `done`, plus `cancelled`) are enforced
by `roadmap-plan` and `roadmap-refine`, not hand-edited here.

Entries carry monotonically increasing IDs starting at `R-1`, never reused.
Outcome IDs (`O-n` in `goals.md`) are an independent counter; the streams never
cross.

The three MVP items below were **delivered before** the planning suite was
adopted, because `gh-plumbing` is a mature, portfolio-wide configuration source.
They're recorded here retroactively as `status: done`, mapped to sprint 1, so the
mission MVP resolves. See `project/mission.md` §Source.

## Phase 1: Shared CI/CD and governance baseline

### R-1: Reusable GitHub Actions workflow library

```yaml
id: R-1
title: Reusable GitHub Actions workflow library
detail: fine
outcomes: [O-1]
target_sprint: 1
mvp: true
status: done
```

The `reusable-*.yaml` workflow library (`pre-commit`, `mkdocs` build and deploy,
spelling and `Vale`, `automerge`, release-drafter and publish, Docker lint,
build, and publish, Ansible molecule and galaxy, Terraform lint, `Trivy`,
chain-bench, dependency-review, Node.js and Python coverage) that downstream
`nolte/*` repositories call via
`uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`.
Capability `reusable-github-actions-workflows` in `project/portfolio.yml`.

### R-2: Probot configuration commons

```yaml
id: R-2
title: Probot configuration commons
detail: fine
outcomes: [O-2]
target_sprint: 1
mvp: true
status: done
```

The shared `.github/commons-*.yml` `Probot` presets (settings, boring-cyborg,
release-drafter, stale) that downstream repositories inherit via `_extends:` so
labels, branch protection, and housekeeping stay uniform across the portfolio.
Capability `probot-commons-config` in `project/portfolio.yml`.

### R-3: Renovate shared presets

```yaml
id: R-3
title: Renovate shared presets
detail: fine
outcomes: [O-3]
target_sprint: 1
mvp: true
status: done
```

The `renovate-configs/common` preset that downstream repositories extend via
`extends: ["github>nolte/gh-plumbing//renovate-configs/common"]` for consistent
dependency-update grouping, scheduling, and labelling. Capability
`renovate-shared-presets` in `project/portfolio.yml`.
