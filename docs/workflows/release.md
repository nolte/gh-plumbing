# Release

Release handling spans two workflows and one Probot configuration.

- **`reusable-release-drafter.yml`** maintains the draft release with a generated changelog as PRs land.
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
    Release-drafter buckets PRs by label. [commons-settings](../probot/settings.md) declares the shared label palette; [boring-cyborg](../probot/labelling.md) applies the labels to each PR.

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
       include "../../.github/workflows/reusable-release-drafter.yml"
    %}
    ```

=== "Refresh master workflow"

    ```yaml
    {%
       include "../../.github/workflows/reusable-release-cd-refresh-master.yml"
    %}
    ```

=== "Release drafter Probot configuration"

    ```yaml
    {%
       include "../../.github/commons-release-drafter.yml"
    %}
    ```
