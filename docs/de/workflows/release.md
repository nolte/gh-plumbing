# Release

Das Release-Handling erstreckt sich über zwei Workflows und eine Probot-Konfiguration.

- **`reusable-release-drafter.yml`** pflegt den Release-Entwurf mit generiertem Changelog, sobald Pull Requests gemerged werden.
- **`reusable-release-cd-refresh-master.yml`** mergt den veröffentlichten Release-Tag in `master`, damit `master` immer dem aktuellen Release entspricht.
- **`_extends: gh-plumbing:.github/commons-release-drafter.yml`** liefert die geteilte Release-Drafter-Kategorisierung.

---

## Release-Entwürfe

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

!!! tip "Kategorisierung"
    Release-Drafter sortiert PRs anhand von Labels. [commons-settings](../probot/settings.md) deklariert die geteilte Label-Palette; [boring-cyborg](../probot/labelling.md) hängt die Labels an die einzelnen PRs.

---

## `master` beim Release auffrischen

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

!!! warning "Direkte Commits auf master"
    Commit nicht direkt auf `master` — der Workflow überschreibt deine Änderungen beim nächsten Release.

---

## Zentrale Konfiguration

=== "Release-Drafter-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-drafter.yml"
    %}
    ```

=== "Refresh-master-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-cd-refresh-master.yml"
    %}
    ```

=== "Release-Drafter-Probot-Konfiguration"

    ```yaml
    {%
       include "../../../.github/commons-release-drafter.yml"
    %}
    ```
