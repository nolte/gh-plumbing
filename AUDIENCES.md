# Audiences for gh-plumbing

<!--
Produced via the `audience-identify` skill, following
spec/project/audience-identification/.
Do not add audiences without first declaring the bounded context below.
-->

## Bounded context

`gh-plumbing` is a configuration-only repository that publishes two
asset classes for downstream GitHub repositories:

1. **Reusable GitHub Actions workflows** (`.github/workflows/reusable-*.y{a}ml`),
   consumed via `uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>`.
2. **Shared Probot and tool configurations**: `.github/commons-*.yml` consumed
   via Probot's `_extends:` mechanism, and `renovate-configs/common.json`
   consumed via `github>nolte/gh-plumbing//renovate-configs/common`.

**Inside the boundary:** the contents of `.github/workflows/reusable-*`,
`.github/commons-*.yml`, `renovate-configs/`, and the mkdocs site
(`docs/`, `mkdocs.yml`) that documents the published surface.

**Outside the boundary:** this repository's own dog-fooding wrapper
workflows (`build-static-tests.yaml`, `release-cd-refresh-master.yml`,
`release-drafter.yml`, `automerge.yaml`, `stale.yaml`, `spelling.yaml`,
`dependency-review.yaml`). These consume the reusable workflows but are
not part of the published surface. Application code of any kind also
sits outside the boundary, and the repository contains none.

## Audiences

Each entry: label, relationship category, interaction surface, expectation,
open questions, `confirmed` or `assumed`, criticality (primary / secondary /
peripheral). Mark a whole category as `none — <reason>` when it doesn't apply.

### Direct consumers

- **Downstream repositories consuming reusable workflows**, _category_:
  direct-consumer · _surface_:
  `uses: nolte/gh-plumbing/.github/workflows/reusable-*.yaml@<tag>` in
  their own workflow files · _expects_: stable input and secret
  contracts; breaking changes only with lead time; reproducible outputs;
  **every published tag must be a usable pinning target** (consumers
  pin to tags, not to `@develop`) · _status_: `confirmed` ·
  _criticality_: primary
  - Open questions: none
- **Downstream repositories extending Probot configurations**,
  _category_: direct-consumer · _surface_:
  `_extends: gh-plumbing:.github/commons-<name>.yml` in their
  `.github/settings.yml`, `.github/boring-cyborg.yml`,
  `.github/release-drafter.yml` · _expects_: consistent
  label and branch-protection definitions; visible diffs when commons
  configurations change, because changes propagate immediately on the
  next Probot sync · _status_: `assumed` · _criticality_: primary
  - Open questions: which downstream repositories actually consume which
    `commons-*.yml` file?
- **Downstream repositories consuming Renovate presets**, _category_:
  direct-consumer · _surface_:
  `extends: ["github>nolte/gh-plumbing//renovate-configs/common"]` in
  their `renovate.json` · _expects_: vetted Renovate defaults; no
  surprise changes to update cadence or grouping behaviour ·
  _status_: `assumed` · _criticality_: primary
  - Open questions: do consumers pin to a ref (`#<sha>` / `#<tag>`) or
    track the default branch via the bare path?

### Operators

- `none — <reason>`: gh-plumbing is a passive asset repository, with no
  running service, no deployment targets, no dashboards, and no on-call
  rotation. The bots that consume the published configurations (Probot
  Settings App, Renovate, GitHub Actions runners) run outside the
  bounded-context boundary and aren't operated from this repository.

### Contributors / maintainers

- **Repository maintainer (`nolte`)**, _category_: contributor-maintainer
  · _surface_: direct push or PR on `develop`; local tool chain (`asdf`,
  `task`, `pre-commit`, `mkdocs`); Vale in CI; `CLAUDE.md` for
  AI-assisted edits · _expects_: working local tool chain; green CI
  checks; release automation that maintains the changelog · _status_:
  `assumed` · _criticality_: primary
  - Open questions: none
- **External pull-request contributors**, _category_:
  contributor-maintainer · _surface_: fork then open a PR;
  `boring-cyborg.yml` welcome comments; `commons-settings.yml` labels;
  `automerge.yaml` for labelled maintainer PRs · _expects_: readable
  contribution docs (README, docs site); CI feedback without insider
  context; clear conventions for what a reusable-workflow contract is ·
  _status_: `assumed` · _criticality_: peripheral
  - Open questions: are there external contributors at meaningful
    volume, or is this audience theoretical?
- **Renovate bot**, _category_: contributor-maintainer · _surface_: PRs
  targeting `renovate.json`, `.tool-versions` pins, and reusable-workflow
  action versions; automatic merging via the `automerge` label when
  checks are green · _expects_: stable CI so automatic merges land;
  consistent label application · _status_: `assumed` · _criticality_:
  secondary
  - Open questions: none

### Governing parties

- `none — <reason>`: no compliance owner, no security review board, and
  no legal or Service Level Agreement (SLA) party on the other side. The
  repository is personal OSS without organisational governance. Upstream
  tool schemas (Probot Settings App, Renovate, release-drafter,
  `pascalgn/automerge-action`, Vale) constrain the published structure
  but are interface contracts, not governance audiences in the spec
  sense.

### Indirect audiences

- **Security-conscious downstream users and supply chain reviewers**,
  _category_: indirect · _surface_: read the public repository, commit
  history, and reusable workflow source · _expects_: tag immutability;
  release notes that support auditing; conservative permissions in
  reusable workflows; pinned upstream actions · _status_: `assumed` ·
  _criticality_: secondary
  - Open questions: are there explicit reviewers (security teams in
    downstream organisations) the maintainer should communicate with
    directly?
- **Open-source readers seeking patterns**, _category_: indirect ·
  _surface_: published mkdocs site (`has_pages: true`); public README;
  browsing the GitHub repository · _expects_: working examples of
  reusable workflows and Probot `_extends:` for adoption in their own
  projects · _status_: `assumed` · _criticality_: peripheral
  - Open questions: none

## Open questions (cross-cutting)

- D1's `confirmed` rating covers the existence of the audience and the
  tag-pinning behaviour. Concrete contracts (which inputs and secrets
  each reusable workflow guarantees stable; deprecation policy length)
  aren't yet codified in any spec.
- The mkdocs site doubles as I2's interaction surface but lacks an audit
  for that audience, so see `docs-freshness-checker` for routine drift
  checks.

## Revisit triggers

- A new reusable workflow lands under `.github/workflows/reusable-*.y{a}ml`
  (changes the published surface).
- A new `commons-*.yml` file lands under `.github/` (new Probot extension
  point for downstream repositories).
- The pinning convention changes (for example `@develop` shifting to an
  enforced `@vX.Y` in documentation, or the introduction of
  major-version tag aliases like `@v1`).
- The maintainer identifies a downstream consumer at organisational
  scale (which would promote D2 and D3 to `confirmed` and may introduce
  a Governing-parties entry).
- Someone adds application code to the repository (which would
  invalidate the "configuration-only" bounded-context premise).
