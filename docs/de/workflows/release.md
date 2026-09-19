# Release

Das Release-Handling erstreckt sich über drei Workflows und eine Probot-Konfiguration.

- **`reusable-release-drafter.yml`** pflegt den Release-Entwurf mit generiertem Changelog, sobald Pull Requests gemerged werden.
- **`reusable-release-publish.yml`** befördert den offenen Entwurf zu einem veröffentlichten Release für einen bestimmten Tag, mit optionalem Dry-Run-Validierungs-Gate.
- **`reusable-release-cd-refresh-master.yml`** richtet den Präsentationsbranch auf den veröffentlichten Release-Tag aus, damit er immer dem aktuellen Release entspricht. Er liest die Protection des Ziels und wählt die Schreibstrategie daraus: einen Merge-Commit, wo Merge-Commits erlaubt sind, einen `force-with-lease`-Reset, wo sie es nicht sind, und eine laute Verweigerung, wo das Ziel beides verbietet. Siehe [ADR-001](../decisions/adr-001-presentation-branch-reset.md).
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
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-drafter.yml@<tag>
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

### Probot

```yaml title=".github/release-drafter.yml"
_extends: gh-plumbing:.github/commons-release-drafter.yml
```

!!! tip "Kategorisierung"
    Release-Drafter sortiert PRs anhand von Labels. [commons-settings](../probot/settings.md) deklariert die geteilte Label-Palette, und [boring-cyborg](../probot/labelling.md) hängt die Labels an die einzelnen PRs.

---

## Release veröffentlichen

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

!!! note "Tag muss zu einem bestehenden Entwurf passen"
    `tag` muss zum Tag eines bestehenden Release-Drafter-Entwurfs passen. Es
    gibt keine „neuester gewinnt"-Heuristik — existiert kein Entwurf für den
    angegebenen Tag, scheitert der Workflow sofort. Zuvor den
    Draft-Workflow auf `develop` laufen lassen.

!!! tip "Dry Run"
    `dry_run: true` setzen, um jeden Validierungs-Gate auszuführen, ohne den
    Entwurf zu einem veröffentlichten Release umzuschalten. Nützlich, um den
    Publish-Pfad vor dem eigentlichen Release zu verifizieren.

!!! warning "Das Publizieren verweigert sich, wenn die Kaskade nicht laufen kann"
    Vor dem Umschalten prüft der Workflow, ob `release-cd-refresh-master.yml`
    existiert und aktiv ist. Ein Release, das in eine tote Kaskade hinein
    veröffentlicht wird, lässt den Präsentationsbranch hinter einem grünen
    Lauf zurück — so blieb `v2.0.0` hier sechs Wochen unbemerkt.

    Ein Repository, das bewusst keinen Präsentationsbranch führt, setzt
    `require-cascade: false`. Das Gate verweigert weiterhin, wenn der Workflow
    existiert und abgeschaltet ist: eine vorhandene, deaktivierte Kaskade ist
    etwas anderes als eine, die niemand wollte.

    | Input | Default | Wirkung |
    | --- | --- | --- |
    | `require-cascade` | `true` | Verlangt vor dem Publizieren, dass der Kaskaden-Workflow existiert und aktiv ist |

---

## `master` beim Release auffrischen

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

!!! warning "Direkte Commits auf master"
    Nicht direkt auf `master` committen — der Workflow überschreibt lokale Änderungen beim nächsten Release.

---

## Zentrale Konfiguration

=== "Release-Drafter-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-drafter.yml"
    %}
    ```

=== "Release-Publish-Workflow"

    ```yaml
    {%
       include "../../../.github/workflows/reusable-release-publish.yml"
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
