# Roadmap

This file is the work queue governed by `spec/project/roadmap/`. Each entry is a
level-3 heading followed by a `yaml` code block (`id`, `title`, `detail`,
`outcomes`, `target_sprint`, `mvp`, `status`, in that order) and a free-text
body. `roadmap-plan` and `roadmap-refine` own the detail level (`detail`: `fine`
/ `coarse` / `backlog`) and the status lifecycle (`status`: `proposed`,
`active`, `done`, plus `cancelled`). Don't hand-edit those fields here.

Entries carry monotonically increasing IDs starting at `R-1`, never reused.
Outcome IDs (`O-n` in `goals.md`) are an independent counter. The two streams
never cross.

`gh-plumbing` shipped the three minimum-viable-product items below before
adopting the planning suite, because it's a mature, portfolio-wide
configuration source. This roadmap records them retroactively as `status: done`,
mapped to sprint 1, so the mission's minimum viable product resolves. See
`project/mission.md` §Source.

## Phase 1: Shared delivery and governance baseline

### R-1: Reusable workflow library

```yaml
id: R-1
title: Reusable GitHub Actions workflow library
detail: fine
outcomes: [O-1]
target_sprint: 1
mvp: true
status: done
```

The `reusable-*.yaml` workflow library covers linting, docs, spelling, test
coverage, container build and publish, Ansible and Terraform checks, release
automation, and security scanning. The README §Workflows lists the full
catalogue. Downstream `nolte/*` repositories call it via
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

The `Probot` presets cover four areas: settings, boring-cyborg, release-drafter,
and stale. A downstream repository inherits them by extending the shared commons
file. Governance stays uniform across the portfolio. Capability
`probot-commons-config` in `project/portfolio.yml`.

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

The `renovate-configs/common` preset. Downstream repositories extend it via
`extends: ["github>nolte/gh-plumbing//renovate-configs/common"]`. It gives
consistent dependency-update grouping, scheduling, and labelling. Capability
`renovate-shared-presets` in `project/portfolio.yml`.
