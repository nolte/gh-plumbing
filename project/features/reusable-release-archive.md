---
id: F-2
title: Reusable release archive with build provenance
status: in_progress
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
      target: .github/workflows/reusable-release-publish.yml
      resolution: proceed
      evidence: "reusable-release-publish.yml:147-208 (draft resolution), :601-671 (HACS asset built at TARGET_SHA, dry-run skip :661-665, gh release upload --clobber :669)"
    - kind: prior-art
      target: .github/workflows/reusable-docker-publish.yaml
      resolution: proceed
      evidence: "reusable-docker-publish.yaml:68-79 (job-level id-token/attestations, callers must grant both), :181-184 (actions/attest-build-provenance); docs/en/workflows/container.md:37-49"
    - kind: prior-art
      target: spec/project/github-actions-best-practices/en.md §H, spec/project/continuous-delivery/en.md §B/§C
      resolution: proceed
      evidence: "github-actions-best-practices/en.md:101-102; continuous-delivery/en.md:54, :57, :62-65"
    - kind: drift
      target: spec/project/branching-model/en.md, spec/project/project-structure/en.md, spec/project/release-automation/en.md
      resolution: proceed
      evidence: "branching-model/en.md:66, project-structure/en.md:51, release-automation/en.md:24 describe packaging as post-publish (SHOULD/MAY); release-automation/en.md:49 forbids altering the release body"
---

## Description

A consumer repository that ships a release archive calls the new
`reusable-release-archive.yml` from its release workflow, ahead of
`release-publish` and ordered by `needs:`. It hands in a Task target and one or
more asset paths or globs. The workflow runs the target at the draft tag's
target commit, attests every matching file with
`actions/attest-build-provenance`, and attaches each file to the
release-drafter draft. The release therefore never appears public without its
asset, and the path keeps working once GitHub immutable releases are enabled.

`id-token: write` and `attestations: write` sit on the producing job only. The
HACS asset path in `reusable-release-publish.yml` stays as it is.

## Acceptance criteria

- [x] **acceptance-1** A call with a Task target and an asset glob attaches every matching file to the draft release, and `gh attestation verify` succeeds for each file.
- [ ] **acceptance-2** An asset glob that matches no file, a failed attestation, or a target release that's already published each fail the run without modifying the release.
- [x] **acceptance-3** A `dry-run` call builds and attests but uploads nothing.
- [x] **acceptance-4** A re-run replaces same-named assets on the draft.
- [x] **acceptance-5** A consumer that doesn't call the new workflow needs no new permission on any calling job.
- [x] **acceptance-6** The consumer documentation states that the calling job grants `id-token: write` and `attestations: write`, and that missing either one fails the run at startup.
- [x] **acceptance-7** The workflow never changes the release body, name, or draft and prerelease flags.

## Test hooks

- **acceptance-1** — `test-release-archive.yml` positive scenario: `archive-first` attaches `fixture-a.zip` and `fixture-b.zip` to a throwaway draft, `verify` runs `gh attestation verify --signer-workflow … --source-digest` per asset (run 43956030663 and the run at `b65c3de` on #457) — passing
- **acceptance-2** — `test-release-archive.yml` dispatch scenarios `negative-empty-glob` and `negative-published` (red run by design, `verify` job green), run on `develop` after #457 merges; the forced-attestation-failure part is review-only per operator decision 2026-11-16 (attest precedes upload in the same job, so a failed attestation stops the job before any upload) — pending
- **acceptance-3** — `test-release-archive.yml` positive scenario: `archive-dry` green, `verify` asserts the dry-run draft carries no asset — passing
- **acceptance-4** — `test-release-archive.yml` positive scenario: `archive-again` against the same draft, `verify` asserts unchanged asset names and changed content digests — passing
- **acceptance-5** — review of `permissions:` in `reusable-release-archive.yml` (workflow level `contents: read`, write scopes on jobs only) and of existing callers, by `nolte-shared:cicd-pipeline-reviewer` on #457 — passing
- **acceptance-6** — review of `docs/en/workflows/release-archive.md` and `docs/de/workflows/release-archive.md` (danger admonition on `contents`, `id-token`, `attestations` write and `startup_failure`) — passing
- **acceptance-7** — `test-release-archive.yml` positive scenario: `verify` compares body, name, and draft/prerelease flags against the snapshot taken at draft creation — passing

## Consistency notes

**Prior art: `reusable-release-publish.yml`.** Established:
`reusable-release-publish.yml:147-208` resolves the single draft, and `:601-671`
builds the HACS asset at the target commit, skips upload on dry run
(`:661-665`), and uploads with `--clobber` (`:669`). These are the semantics of
R1 and R4. Requirement R2 forbids changing that file, so F-2 copies the
semantics into the new reusable instead of extracting them. Resolution: proceed.

**Prior art: attestation in `reusable-docker-publish.yaml`.** Established:
`reusable-docker-publish.yaml:68-79` declares `id-token` and `attestations` at
job level with the warning that callers must grant both, and `:181-184` runs
`actions/attest-build-provenance`. F-2 reuses that pattern. Acceptance-5 holds
only for non-callers; a caller has to grant both scopes or the run ends in
`startup_failure`, which acceptance-6 documents. Resolution: proceed.

**Prior art: the spec already requires attestation.** Established:
`github-actions-best-practices/en.md:101-102` asks for platform attestation with
permissions on the producing job only, and `continuous-delivery/en.md:57`
requires the asset to be re-fetchable at the moment the release is declared
shipped. F-2 binds those rules; nothing contradicts. Resolution: proceed.

**Drift: packaging is described as post-publish.** Established:
`branching-model/en.md:66`, `project-structure/en.md:51`, and
`release-automation/en.md:24` describe archive packaging on
`release: [published]`. These are SHOULD/MAY conventions, so F-2's pre-publish
path doesn't break a MUST, and it satisfies `continuous-delivery` §B better.
`release-automation/en.md:49` forbids altering the release body, which
acceptance-7 makes explicit. Naming the pre-publish reusable as the preferred
path in the spec is left to F-4 or F-6. Resolution: proceed.

## Risks

- The pre-publish build runs in the caller's release workflow; a slow Task
  target delays every publish.
- Requirement R2 keeps two copies of the draft-resolution logic (HACS path and
  this reusable) until a later refactor merges them.

## References

- `project/requirements/release-archive-provenance.md` R1–R4, AC1
- nolte/gh-plumbing#446
