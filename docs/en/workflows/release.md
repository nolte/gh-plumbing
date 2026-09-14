# Release

Release handling spans three workflows and one Probot configuration.

- **`reusable-release-drafter.yml`** maintains the draft release with a generated changelog as PRs land.
- **`reusable-release-publish.yml`** promotes the open draft to a published release for a given tag, with an optional dry-run validation gate.
- **`reusable-release-cd-refresh-master.yml`** points the presentation branch at the published release tag, so it always tracks the latest release. It reads the target's protection and picks the write strategy from it: a merge commit where merge commits are permitted, a force-with-lease reset where they aren't, and a loud refusal where the target permits neither. See [ADR-001](../decisions/adr-001-presentation-branch-reset.md).
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
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-drafter.yml@<tag>
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
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@<tag>
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

!!! warning "Publishing refuses when the cascade can't run"
    Before the flip, the workflow checks that
    `release-cd-refresh-master.yml` exists and is active. A release published
    into a dead cascade leaves the presentation branch stale behind a green
    run, which is how `v2.0.0` went unnoticed here for six weeks.

    A repository that deliberately keeps no presentation branch sets
    `require-cascade: false`. The gate still refuses when the workflow exists
    and is switched off, because a cascade that's present and disabled is a
    different fact from one nobody wanted.

    | Input | Default | Effect |
    | --- | --- | --- |
    | `require-cascade` | `true` | Require the cascade workflow to exist and be active before publishing |

---

## Refresh `master` on release

```yaml title=".github/workflows/release-cd-refresh-master.yml"
on:
  release:
    types: [published]

jobs:
  refresh_presentation_branch:
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-cd-refresh-master.yml@<tag>
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
