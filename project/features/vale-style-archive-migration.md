---
id: F-5
title: vale-style publishes its archive through the reusable step
status: ready
roadmap_item: R-4
sprint: 2
created: 2026-11-15
ended: null
verifies_sprint_value: acceptance-2
consistency_check:
  performed_at: 2026-11-15
  agent_version: feature-consistency-reviewer@3845114
  findings:
    - kind: drift
      target: F-3
      resolution: revisit-after a gh-plumbing release containing F-2 is published
      evidence: "project/requirements/release-archive-provenance.md R8 (depends on a release with strand A); vale-style extends the Renovate preset at #v1.1.12 without pinDigests"
    - kind: prior-art
      target: .vale.ini, renovate-configs/common.json
      resolution: proceed
      evidence: ".vale.ini:4 (vale-style/releases/download/v0.1.17/nolte-styles.zip); renovate-configs/common.json:50-56 (custom manager on nolte/vale-style/releases/download/<version>/)"
    - kind: prior-art
      target: spec/project/github-actions-best-practices/en.md §E
      resolution: proceed
      evidence: "github-actions-best-practices/en.md:77-78 (consume identical logic from gh-plumbing, no consumer-local copy); continuous-delivery/en.md:57"
---

## Description

Once a gh-plumbing release ships F-2, nolte/vale-style builds and publishes its
`nolte-styles.zip` through `reusable-release-archive.yml`, with Task target
`build` and asset `build/nolte-styles.zip`, and deletes its local
`release-cd-archive.yml`. Consumers downloading the style package get an
archive that's attached at the moment of publish and carries a verifiable
build-provenance attestation, and the drafted release notes survive publish.

## Acceptance criteria

- [ ] **acceptance-1** The next vale-style release carries `nolte-styles.zip` at the moment it's published.
- [ ] **acceptance-2** `gh attestation verify` succeeds for that `nolte-styles.zip`.
- [ ] **acceptance-3** The release body drafted by release-drafter is intact after publish.
- [ ] **acceptance-4** `release-cd-archive.yml` no longer exists in nolte/vale-style.
- [ ] **acceptance-5** The call to `reusable-release-archive.yml` is pinned to a commit digest with a trailing tag comment.
- [ ] **acceptance-6** The asset name `nolte-styles.zip` and its download path stay unchanged, so `.vale.ini` packages and the Renovate custom manager keep resolving.

## Test hooks

- **acceptance-1**: `gh release view <tag> -R nolte/vale-style --json assets` right after publish; pending
- **acceptance-2**: `gh attestation verify nolte-styles.zip -R nolte/vale-style`; pending
- **acceptance-3**: `gh release view <tag> -R nolte/vale-style --json body`, non-empty and matching the draft; pending
- **acceptance-4**: `gh api repos/nolte/vale-style/contents/.github/workflows`; pending
- **acceptance-5**: manual review of vale-style's release workflow; pending
- **acceptance-6**: `vale sync` in gh-plumbing against the new release; pending

## Consistency notes

**Drift: ordering against F-2 and F-3.** Established from the requirements
artifact: R8 depends on a gh-plumbing release containing strand A, and
vale-style extends the Renovate preset at `#v1.1.12` without `pinDigests`. F-5
can't start before F-2 ships, and its new `uses:` must be digest-pinned by hand
or vale-style's `actionlint` check turns red once it bumps past F-3, which
acceptance-5 covers. Resolution: revisit after a gh-plumbing release containing
F-2 is published.

**Prior art: the asset is a portfolio contract.** Established: `.vale.ini:4`
downloads `nolte-styles.zip` from vale-style releases, and
`renovate-configs/common.json:50-56` tracks that path with a custom manager.
Acceptance-6 keeps both intact. Resolution: proceed.

**Prior art: the spec asks consumers to drop local copies.** Established:
`github-actions-best-practices/en.md:77-78` asks consumers to call shared logic
from gh-plumbing rather than keep a local copy, which is exactly the retirement
of `release-cd-archive.yml`. Established by reading
`nolte/vale-style` `origin/develop:.github/workflows/release-cd-archive.yml`
(the reviewer's scan didn't reach it): it runs on `release: [published]`, builds
with `task build`, uploads with `gh release upload` without `--clobber`, and
offers a `workflow_dispatch` `tag` input for manual recovery on an existing
release. Its actions are already digest-pinned. Retiring it drops that recovery
path; R4e makes F-2 refuse a published release on purpose. Resolution: proceed,
with the lost recovery path recorded under Risks.

## Risks

- Lands in another repository (nolte/vale-style) and depends on a gh-plumbing
  release, so it can't share a sprint slot with F-2 before that release exists.
- Deleting `release-cd-archive.yml` removes its `workflow_dispatch` recovery
  path for attaching the archive to an already-published release; after F-5 a
  failed pre-publish build is fixed by re-running before publish, never after.

## References

- `project/requirements/release-archive-provenance.md` R8, AC2, AC4
- nolte/gh-plumbing#446
