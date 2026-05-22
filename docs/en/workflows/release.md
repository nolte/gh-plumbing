# Release

Release handling spans three workflows and one Probot configuration.

- **`reusable-release-drafter.yml`** maintains the draft release with a generated changelog as PRs land.
- **`reusable-release-publish.yml`** promotes the open draft to a published release for a given tag, with an optional dry-run validation gate.
- **`reusable-release-cd-refresh-master.yml`** merges the published release tag into `master` so `master` always tracks the latest release.
- **`_extends: gh-plumbing:.github/commons-release-drafter.yml`** provides shared release-drafter categorization.

---

## Draft releases

### Workflow

```yaml title=".github/workflows/release-drafter.yml"
on:
  push:
    branches:
      - develop

jobs:
  update_release_draft:
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-drafter.yml@develop
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

### Probot

```yaml title=".github/release-drafter.yml"
_extends: gh-plumbing:.github/commons-release-drafter.yml
```

!!! tip "Categorization"
    Release-drafter buckets PRs by label. [commons-settings](../probot/settings.md) declares the shared label palette, and [boring-cyborg](../probot/labelling.md) applies the labels to each PR.

---

## Publish a release

```yaml title=".github/workflows/release-publish.yml"
on:
  workflow_dispatch:
    inputs:
      tag:
        description: "Tag to publish (must match an open release-drafter draft)."
        required: true
        type: string
      dry_run:
        description: "Validate without flipping draft=false."
        required: false
        type: boolean
        default: false

jobs:
  publish:
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@develop
    with:
      tag: ${{ inputs.tag }}
      dry_run: ${{ inputs.dry_run }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! note "Tag must match an existing draft"
    `tag` must match the tag on an existing release-drafter draft. There is no
    "newest wins" heuristic—if no draft exists for the given tag the workflow
    fails fast. Run the draft workflow on `develop` first.

!!! tip "Dry run"
    Set `dry_run: true` to run every validation gate without flipping the
    draft to a published release. Useful for verifying the publish path
    before the actual release.

---

## Refresh `master` on release

```yaml title=".github/workflows/release-cd-refresh-master.yml"
on:
  release:
    types: [published]

jobs:
  refresh_presentation_branch:
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-cd-refresh-master.yml@develop
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! warning "Direct commits to master"
    Don't commit to `master` directly—the workflow will overwrite your changes on the next release.

---

## Central configuration

=== "Release drafter workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-drafter.yml"
    %}
    ```

=== "Release publish workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-publish.yml"
    %}
    ```

=== "Refresh master workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-cd-refresh-master.yml"
    %}
    ```

=== "Release drafter Probot configuration"

    ```yaml
    {%
       include "../../../.github/commons-release-drafter.yml"
    %}
    ```
