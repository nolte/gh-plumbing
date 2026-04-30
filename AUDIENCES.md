# Audiences — gh-plumbing

<!--
Produced via the `audience-identify` skill, following
spec/project/audience-identification/.
Do not add audiences without first declaring the bounded context below.
-->

## Bounded context

`gh-plumbing` is a configuration-only repository that publishes two asset
classes for downstream GitHub repositories:

1. **Reusable GitHub Actions workflows** (`.github/workflows/reusable-*.y{a}ml`),
   consumed via `uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`.
2. **Shared Probot and tool configurations**: `.github/commons-*.yml` consumed
   via Probot's `_extends:` mechanism, and `renovate-configs/common.json`
   consumed via `github>nolte/gh-plumbing//renovate-configs/common`.

**Inside the boundary:** the contents of `.github/workflows/reusable-*`,
`.github/commons-*.yml`, `renovate-configs/`, and the MkDocs site
(`docs/`, `mkdocs.yml`) that documents the published surface.

**Outside the boundary:** this repo's own dog-fooding wrapper workflows
(`build-static-tests.yaml`, `release-cd-refresh-master.yml`,
`release-drafter.yml`, `automerge.yaml`, `stale.yaml`, `spelling.yaml`,
`dependency-review.yaml`). These consume the reusable workflows but are
not part of the published surface. Application code of any kind is also
outside — the repo contains none.

## Audiences

Each entry: label, relationship category, interaction surface, expectation,
open questions, `confirmed` or `assumed`, criticality (primary / secondary /
peripheral). Mark a whole category as `none — <reason>` when it does not apply.

### Direct consumers

- **Downstream repos consuming reusable workflows** — _category_: direct-consumer ·
  _surface_: `uses: nolte/gh-plumbing/.github/workflows/reusable-*.yaml@<tag>`
  in their own workflow files · _expects_: stable input/secret contracts;
  breaking changes only with lead time; reproducible outputs; **every
  published tag must be a usable pinning target** (consumers pin to tags,
  not to `@develop`) · _status_: `confirmed` · _criticality_: primary
  - Open questions: none
- **Downstream repos extending Probot configs** — _category_: direct-consumer ·
  _surface_: `_extends: gh-plumbing:.github/commons-<name>.yml` in their
  `.github/settings.yml`, `.github/boring-cyborg.yml`,
  `.github/release-drafter.yml` · _expects_: consistent
  label / branch-protection definitions; visible diffs when commons configs
  change, because changes propagate immediately on the next Probot sync
  · _status_: `assumed` · _criticality_: primary
  - Open questions: which downstream repos actually consume which
    `commons-*.yml` file?
- **Downstream repos consuming Renovate presets** — _category_: direct-consumer ·
  _surface_: `extends: ["github>nolte/gh-plumbing//renovate-configs/common"]`
  in their `renovate.json` · _expects_: vetted Renovate defaults; no
  surprise changes to update cadence or grouping behaviour
  · _status_: `assumed` · _criticality_: primary
  - Open questions: do consumers pin to a ref (`#<sha>` / `#<tag>`) or
    track the default branch via the bare path?

### Operators

- `none — gh-plumbing is a passive asset repository: no running service,
  no deployment targets, no dashboards, no on-call rotation. The bots that
  consume our configs (Probot Settings App, Renovate, GitHub Actions
  runners) run outside the bounded-context boundary and are not operated
  by us.`

### Contributors / maintainers

- **Repo maintainer (`nolte`)** — _category_: contributor-maintainer ·
  _surface_: direct push / PR on `develop`; local toolchain (`asdf`, `task`,
  `pre-commit`, `mkdocs`); Vale in CI; `CLAUDE.md` for AI-assisted edits
  · _expects_: working local toolchain; green CI checks; release automation
  that maintains the changelog · _status_: `assumed` · _criticality_: primary
  - Open questions: none
- **External pull-request contributors** — _category_: contributor-maintainer ·
  _surface_: fork → PR; `boring-cyborg.yml` welcome comments;
  `commons-settings.yml` labels; `automerge.yaml` for labelled
  maintainer PRs · _expects_: readable contribution docs (README, docs site);
  CI feedback without insider context; clear conventions for what a
  reusable-workflow contract is · _status_: `assumed` · _criticality_: peripheral
  - Open questions: are there external contributors at meaningful
    volume, or is this audience theoretical?
- **Renovate bot** — _category_: contributor-maintainer ·
  _surface_: PRs against `renovate.json`, `.tool-versions` pins,
  reusable-workflow action versions; auto-merge via `automerge` label
  when checks are green · _expects_: stable CI so auto-merges land;
  consistent label application · _status_: `assumed` · _criticality_: secondary
  - Open questions: none

### Governing parties

- `none — no compliance owner, no security review board, no legal / SLA
  counterparty. The repo is personal OSS without organisational governance.
  Upstream tool schemas (Probot Settings App, Renovate, release-drafter,
  pascalgn/automerge-action, Vale) constrain our structure but are
  interface contracts, not governance audiences in the spec sense.`

### Indirect audiences

- **Security-conscious downstream users / supply-chain reviewers** —
  _category_: indirect · _surface_: read public repo + commit history +
  reusable workflow source · _expects_: tag immutability; auditable
  release notes; conservative permissions in reusable workflows;
  pinned upstream actions · _status_: `assumed` · _criticality_: secondary
  - Open questions: are there explicit reviewers (downstream-org sec
    teams) we should be communicating with directly?
- **Open-source readers seeking patterns** — _category_: indirect ·
  _surface_: published MkDocs site (`has_pages: true`); public README;
  GitHub repo browse · _expects_: working examples of reusable
  workflows + Probot `_extends:` for adoption in their own projects
  · _status_: `assumed` · _criticality_: peripheral
  - Open questions: none

## Open questions (cross-cutting)

- D1's `confirmed` rating covers the existence of the audience and the
  tag-pinning behaviour. Concrete contracts (which inputs/secrets each
  reusable workflow guarantees stable; deprecation policy length) are
  not yet codified in any spec.
- The MkDocs site doubles as I2's interaction surface but is not
  audited for that audience — see `docs-freshness-checker` for routine
  drift checks.

## Revisit triggers

- A new reusable workflow lands under `.github/workflows/reusable-*.y{a}ml`
  (changes the published surface).
- A new `commons-*.yml` file lands under `.github/` (new Probot extension
  point for downstream repos).
- The pinning convention changes (e.g. `@develop` → enforced `@vX.Y` in
  documentation; introduction of major-version tag aliases like `@v1`).
- A downstream consumer is identified at organisational scale (would
  promote D2/D3 to `confirmed` and may introduce a Governing-parties
  entry).
- Application code is added (would invalidate the "configuration-only"
  bounded-context premise).
