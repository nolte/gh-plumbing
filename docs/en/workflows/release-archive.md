# Release archives

`reusable-release-archive.yml` builds a release archive through a Task target
in your repository, attests its build provenance, and attaches it to the
release-drafter draft **before** you publish the release. The release never
appears public without its asset, and the path keeps working once you enable
GitHub immutable releases.

Run it ahead of `reusable-release-publish.yml` and order the publish job after
it with `needs:`.

## Usage

```yaml title=".github/workflows/release-publish.yml"
name: Release Publish

on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Tag to publish. Leave empty to use the single open draft."
        required: false
        type: string
        default: ""
      dry_run:
        description: "Validate without publishing."
        required: false
        type: boolean
        default: false

permissions:
  contents: read

jobs:
  archive:
    permissions:
      contents: write
      id-token: write
      attestations: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-archive.yml@<tag>
    with:
      tag: ${{ inputs.tag }}
      task-target: build
      assets: |
        build/nolte-styles.zip
      dry-run: ${{ inputs.dry_run }}

  publish:
    needs: archive
    permissions:
      contents: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@<tag>
    with:
      tag: ${{ needs.archive.outputs.tag }}
      dry_run: ${{ inputs.dry_run }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! danger "The calling job must grant `contents`, `id-token`, and `attestations` write"

    Without all three the workflow **does not start**. It doesn't fall back to
    an archive without provenance, and it doesn't run with a reduced token:
    GitHub reports `startup_failure` with zero jobs.

    That failure looks like nothing happened at all, and it happens during a
    release, so it's easy to miss. Grant the scopes on the **job** that calls
    the workflow, not on the workflow, per
    `spec/project/github-actions-best-practices` §B and §H. A repository that
    doesn't call this workflow needs no new permission.

## Inputs

| Input | Default | Effect |
| --- | --- | --- |
| `task-target` | required | Task target that builds the archive, run at the draft's target commit with `RELEASE_TAG` set to the draft tag |
| `assets` | required | Newline-separated paths or globs of the files to attach; `**` matches across directories |
| `tag` | empty | Draft to attach to; empty resolves the single open draft |
| `task-version` | `3.52.0` | Exact Task release that runs the target |
| `dry-run` | `false` | Build and attest, upload nothing |

The workflow returns the resolved `tag`, the `target-sha` it built from, and
the attached file names as `assets`.

## What the workflow guarantees

- **Built from the run's commit.** The provenance record names the commit the
  run is for (`github.sha`) as the source. The workflow therefore requires the
  draft target to equal that commit and fails before the build otherwise.
  Dispatch the release workflow on the branch the draft targets, usually
  `develop`, and don't merge to it before the run ends.
- **Every pattern matches.** A pattern that matches no file fails the run
  before the workflow uploads anything, so the publish job never starts.
  Matched file names must be unique, because a release stores assets by name.
- **Attest before upload.** The workflow attests each file before the upload
  step runs. A failed attestation stops the job, and nothing reaches the draft.
- **Drafts only.** A `tag` that names a published release fails the run
  before the build starts. The workflow checks the draft state again right
  before the upload, in case someone published the release during the build.
- **One upload per draft at a time.** Runs that attach to the same draft
  queue up. GitHub keeps at most one waiting run per draft and cancels an
  older waiting run when a newer one arrives.
- **Asset names stay as built.** File names may use only letters, digits,
  `.`, `_`, `+`, and `-`, and must not start with `.`. GitHub would rename
  other names on upload, so the workflow refuses them.
- **Release metadata stays as it is.** The workflow never edits the release
  body, name, or draft and prerelease flags. A re-run replaces same-named
  assets on the draft.
- **The build has no write access.** The Task target runs in a job with
  read-only `contents` and no OpenID Connect (OIDC) token. Only the job that
  attests and uploads holds the write scopes.

!!! note "This workflow doesn't check whether `develop` reaches the draft target"

    `reusable-release-publish.yml` refuses to publish a draft whose target
    isn't reachable from `develop`. That gate runs in the publish job, after
    this one.

!!! warning "Don't combine this workflow with `auto-align: true`"

    With `auto-align: true`, the publish workflow commits the version bump on
    `develop` and moves the draft target to that commit. The tag then points at
    a commit the archive wasn't built from, and the archive misses the aligned
    version files.

## Remote Taskfile includes

The workflow sets `TASK_X_REMOTE_TASKFILES=1` and runs `task --yes`, so a
Taskfile that includes remote Taskfiles works without a terminal. `--yes`
accepts every remote include unchecked, so pin each include to a commit or a
`checksum:`: an include that follows a branch becomes an unpinned input of the
release build.

## Verify an archive

```sh
gh attestation verify nolte-styles.zip --repo <owner>/<repo> \
  --signer-workflow nolte/gh-plumbing/.github/workflows/reusable-release-archive.yml \
  --source-ref refs/heads/develop
```

The reusable workflow in `nolte/gh-plumbing` signs the record, not a workflow
in your repository, so pass `--signer-workflow`: without it,
`gh attestation verify` expects a signer in `<owner>/<repo>` and fails.
`--source-ref` rejects archives built on any other branch. That matters,
because a run on a feature branch also produces a valid attestation, and so
does a dry run: it builds and attests and only skips the upload.

!!! note "An attestation records origin, not safety"

    It tells you which workflow, commit, and runner produced an archive. It
    makes no claim that the archive is free of vulnerabilities.

## Self-test

`test-release-archive.yml` exercises the workflow on throwaway drafts
that it creates and deletes, so the real release-drafter draft stays
untouched. Pull requests that change the workflow run the positive scenario.
The negative scenarios run through `workflow_dispatch` only, and their run
shows red by design: the `verify` job carries the outcome. Re-run a failed
self-test through the "Re-run all jobs" action, because the first attempt's cleanup has
already deleted its drafts.
