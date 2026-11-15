---
id: F-4
title: Best-practices rule against post-publish release rewrites
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
    - kind: prior-art
      target: spec/project/release-automation/en.md
      resolution: proceed
      evidence: "release-automation/en.md:49 (MUST NOT alter the release body inside the publish workflow); continuous-delivery/en.md:54-55; no clobber/allowUpdates/omitBody/ncipollo/post-publish rule elsewhere in spec/"
    - kind: drift
      target: spec/project/github-actions-best-practices/en.md §J
      resolution: proceed
      evidence: "github-actions-best-practices/en.md:34 (draft-to-published owned by release-automation), :114 (MUST NOT restate rules owned by continuous-delivery/release-automation)"
---

## Description

In `nolte/claude-shared`, `spec/project/github-actions-best-practices/` gains a
platform rule: a step that runs after a release is published MUST NOT rewrite
the release's metadata. `gh release upload` without `--clobber` is the safe
primitive, and `ncipollo/release-action` with `allowUpdates` MUST set
`omitBodyDuringUpdate` and its sibling options, because an update otherwise
empties the body, renames the release to the tag, and clears the draft and
prerelease flags.

A workflow author reading the spec learns why the rule exists: it wiped the
drafted release notes of nolte/vale-style v0.1.14 to v0.1.17.

## Acceptance criteria

- [ ] **acceptance-1** The canonical EN spec states the rule as a MUST, phrased as the platform binding of the `continuous-delivery` §B invariant that it references rather than restates.
- [ ] **acceptance-2** The rule names `gh release upload` without `--clobber` as the safe primitive and the `ncipollo/release-action` `allowUpdates` options that must be set.
- [ ] **acceptance-3** The DE translation is structurally in sync.
- [ ] **acceptance-4** The rationale cites the nolte/vale-style v0.1.14 to v0.1.17 release bodies.

## Test hooks

- **acceptance-1**: manual review in `nolte/claude-shared` plus the `spec-readiness-reviewer` agent; pending
- **acceptance-2**: manual review; pending
- **acceptance-3**: `spec` skill drift check in `nolte/claude-shared`; pending
- **acceptance-4**: manual review; pending

## Consistency notes

**Prior art: release-automation forbids body edits in the publish workflow.**
Established: `release-automation/en.md:49` forbids altering the release body
inside the publish workflow, and `continuous-delivery/en.md:54-55` forbids
republishing under an existing version. A grep over `spec/` for `clobber`,
`allowUpdates`, `omitBody`, `ncipollo`, and `post-publish` finds nothing else,
so F-4 duplicates nothing; it extends the rule to every post-publish step and
must reference these sources. Resolution: proceed.

**Drift: placement in github-actions-best-practices.** Established:
`github-actions-best-practices/en.md:34` leaves the draft-to-published
transition to `release-automation`, and `:114` forbids restating rules owned by
`continuous-delivery` or `release-automation`. The placement is sound only when
the rule is phrased as a platform binding, which acceptance-1 requires.
`release-automation` was rejected as a home because its Non-Goal (`:24`)
excludes post-publish packaging; `continuous-delivery` was rejected because it
is tool-independent. Resolution: proceed.

## Risks

- Lands in another repository (`nolte/claude-shared`); its own PR and release
  cadence apply.

## References

- `project/requirements/release-archive-provenance.md` R7
- nolte/gh-plumbing#446
