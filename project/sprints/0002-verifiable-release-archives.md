---
number: 2
status: planned
started: null
ended: null
value_statement: Consumers of a nolte release archive can verify where it was built, and it's attached before the release goes public.
artifact_ref: null
last_commit: null
roadmap_items: [R-4]
features: [F-2, F-3, F-4, F-5, F-6]
---

## Goal

A consumer who downloads a release archive from a `nolte/*` repository runs
`gh attestation verify` against it and learns which workflow built it. The
archive reaches the draft before the release becomes public, so no window exists in
which the release lacks its asset. The sprint delivers roadmap item R-4 from
issue #446:

- F-2 adds `reusable-release-archive.yml`. It builds a Task-built archive,
  attests it, and attaches it to the draft before publish.
- F-3 makes the shared `actionlint` check refuse every external `uses:` that
  isn't pinned to a commit digest.
- F-4 adds a best-practices rule: steps after publish never rewrite release
  metadata.
- F-5 moves `nolte/vale-style` onto the reusable workflow for
  `nolte-styles.zip`.
- F-6 makes the specification corpus require digest pins for
  `nolte/gh-plumbing` and own-org references.

Order inside the sprint: F-5 starts once a gh-plumbing release that contains
F-2 exists. F-4 and F-6 both edit `github-actions-best-practices` in
`nolte/claude-shared`, so their pull requests land one after the other. F-6
lands no later than the release that ships F-3.

F-5 `acceptance-2` verifies the sprint value: `gh attestation verify` succeeds
for the `nolte-styles.zip` of the next vale-style release.

## Features

- [F-2](../features/reusable-release-archive.md): Reusable release archive with build provenance, status: ready
- [F-3](../features/unpinned-action-check.md): Refuse non-digest-pinned actions in the shared `actionlint` check, status: ready
- [F-4](../features/post-publish-metadata-rule.md): Best-practices rule against post-publish release rewrites, status: ready
- [F-5](../features/vale-style-archive-migration.md): vale-style publishes its archive through the reusable step, status: ready
- [F-6](../features/spec-digest-pin-alignment.md): Align the specification corpus on digest pins for portfolio workflow references, status: ready

## Out of scope

- Tag-pinned third-party actions in the `dockerfile-best-practices`
  specification. Issue 743 in the shared Claude plugin repository tracks them,
  a consistency finding of F-6.
- Rolling `reusable-release-archive.yml` out to consumer repositories other
  than `nolte/vale-style`.

## Review notes

_Populated by `sprint-review` at closure._
