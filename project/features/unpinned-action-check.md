---
id: F-3
title: Refuse non-digest-pinned actions in the shared `actionlint` check
status: ready
roadmap_item: R-4
sprint: 2
created: 2026-11-15
ended: null
verifies_sprint_value: null
consistency_check:
  performed_at: 2026-11-15
  agent_version: feature-consistency-reviewer@3845114
  findings:
    - kind: drift
      target: F-1
      resolution: proceed
      evidence: "reusable-workflow-adoption.md:43-44 ('Consumers pin to tags, not to @develop'); workflow-health/en.md:134 accepts a digest whose trailing comment names the release tag"
    - kind: drift
      target: spec/project/github-actions-best-practices/en.md §A, spec/project/release-automation/en.md, spec/project/project-structure/en.md, spec/project/branching-model/en.md
      resolution: split-out F-6
      evidence: "github-actions-best-practices/en.md:45, :48, Open Questions :191, :194; release-automation/en.md:40, :149; project-structure/en.md:143; branching-model/en.md:70"
    - kind: prior-art
      target: renovate-configs/common.json
      resolution: proceed
      evidence: "renovate-configs/common.json:18-22 (pinDigests), :23-28 (digests group); github-actions-best-practices/en.md:42, :46"
    - kind: prior-art
      target: .github/workflows/
      resolution: proceed
      evidence: "every external uses: in reusable-*.y{a}ml is a 40-char SHA with a version comment (e.g. reusable-actionlint.yaml:46, :49); wrappers call ./.github/workflows/..."
    - kind: prior-art
      target: .github/workflows/reusable-actionlint.yaml
      resolution: proceed
      evidence: "reusable-actionlint.yaml:16-23 (fail_level input for staged adoption), :24-31 (actionlint_flags)"
    - kind: drift
      target: docs/en/workflows/index.md
      resolution: proceed
      evidence: "docs/en/workflows/index.md:9-13 teaches @<tag>; @<tag> examples in 12 docs/en files (release.md:24, :58, :102; container.md:27; static-tests.md:18, :42)"
---

## Description

The shared `reusable-actionlint.yaml` gains a `zizmor` step running the
`unpinned-uses` audit. Every external `uses:` reference not pinned to a
40-character commit digest fails the check, with no exemption: `nolte/*`,
`actions/*`, and `github/*` references included. Local `./` references aren't
external and pass. The check fails from the release that ships it, with no
warn-only phase.

A consumer maintainer sees the offending file and line in the check output and
fixes it by pinning the digest with a trailing comment naming the tag, which
the updated workflow documentation shows.

## Acceptance criteria

- [ ] **acceptance-1** A `uses:` pinned to a tag or branch turns the check red and names the file and line.
- [ ] **acceptance-2** Digest-pinned references and local `./` references pass.
- [ ] **acceptance-3** gh-plumbing's own workflows pass the check.
- [ ] **acceptance-4** The `zizmor` step fails regardless of the `fail_level` and `actionlint_flags` inputs.
- [ ] **acceptance-5** Every `nolte/gh-plumbing` usage example under `docs/` (EN and DE) and in this repository's `CLAUDE.md` shows a digest pin with a trailing tag comment; none recommends `@develop` or a bare tag.
- [ ] **acceptance-6** The change ships in a new major release whose release notes announce the breaking change for consumers.

## Test hooks

- **acceptance-1**: fixture workflow with a tag-pinned `uses:`, check run red with file and line in the output; pending
- **acceptance-2**: fixture with a digest pin and a `./` reference, check run green; pending
- **acceptance-3**: `actionlint` job on gh-plumbing's own pull request green; pending
- **acceptance-4**: fixture run with `fail_level: none`, `zizmor` step still red; pending
- **acceptance-5**: `grep -rnE 'nolte/gh-plumbing/.+@(v?[0-9<]|develop|<tag>)' docs CLAUDE.md` returns nothing (24 files under `docs/` matched on 2026-11-15); pending
- **acceptance-6**: manual review of the release tag and release notes; pending

## Consistency notes

**Drift: F-1 acceptance-2 expects tag pins.** Established:
`project/features/reusable-workflow-adoption.md:43-44` says "Consumers pin to
tags, not to `@develop`". Its core intent is to avoid a moving branch, and
`workflow-health/en.md:134` already counts a digest whose trailing comment names
the release tag as resolving to a release. F-3 refines F-1 acceptance-2 rather
than superseding F-1; acceptance-1 and acceptance-3 of F-1 stay valid, and
acceptance-6 here honours F-1 acceptance-3 (breaking changes ship behind a new
tag). Resolution: proceed.

**Drift: the spec corpus requires tags for gh-plumbing references.**
Established, re-read at the cited lines: `release-automation/en.md:40` is a MUST
to pin any `nolte/gh-plumbing` reference to a release tag, `:149` and
`project-structure/en.md:143` carry matching acceptance criteria, and
`github-actions-best-practices/en.md:45` and `:48` accept tags for gh-plumbing
and own-org references. A spec-conformant consumer turns red under F-3.
Resolution: split-out F-6, which aligns the spec on digest plus tag comment and
lands no later than the gh-plumbing release that ships F-3.

**Prior art: digest pinning policy and Renovate.** Established:
`renovate-configs/common.json:18-22` sets `pinDigests` for GitHub Actions, and
`github-actions-best-practices/en.md:42` mandates digests for third-party
actions. F-3 adds enforcement and extends it to `nolte/*`. Renovate's shared
`digests` group (`:23-28`) conflicts with the single-PR rule for gh-plumbing
bumps in `workflow-health`; #447 tracks that, not F-3.
Resolution: proceed.

**Prior art: gh-plumbing already complies.** Established: every external
`uses:` in `.github/workflows/reusable-*.y{a}ml` is a 40-character digest with a
version comment, and the wrappers call `./.github/workflows/...`. Acceptance-3
holds today. Resolution: proceed.

**Prior art: `fail_level` allows staged adoption.** Established:
`reusable-actionlint.yaml:16-23` documents `fail_level` as a way to stage an
adoption. Requirement R6 rules out a warn-only phase, so acceptance-4 keeps the
`zizmor` step independent of it. Resolution: proceed.

**Drift: published docs teach tag pins.** Established:
`docs/en/workflows/index.md:9-13` tells consumers to replace `<tag>` with a
release tag, and 12 pages under `docs/en/` repeat `@<tag>`. The F-6 review
widened this: `docs/en/getting-started/index.md:47-52` recommends `@develop`,
and a grep for `nolte/gh-plumbing/...@(tag|develop)` matches 24 files under
`docs/` in EN and DE; this repository's `CLAUDE.md` also still claims the
wrappers reference `@develop`, while they call `./`. Acceptance-5 covers all of
them. Resolution: proceed.

## Risks

- Accepted in requirements round 7: every consumer that bumps to the release
  goes red until its `nolte/*` references are digest-pinned; where `actionlint`
  is required, the Renovate bump PR itself is blocked.
- nolte/vale-style extends the Renovate preset at `#v1.1.12`, without
  `pinDigests`, so it gets no automated re-pinning.
- `zizmor`'s `unpinned-uses` policy configuration isn't yet verified against the
  version that will be pinned (requirements, assumption).

## References

- `project/requirements/release-archive-provenance.md` R5–R6, AC3
- nolte/gh-plumbing#446
