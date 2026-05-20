# Erste Schritte

`gh-plumbing` bietet drei Integrationsflächen. Wähle die, die zur gewünschten Änderung in deinem Ziel-Repository passt.

---

## Integrationsfläche wählen

<div class="grid cards" markdown>

-   :material-cog-sync: **Reusable Workflow**

    ---

    Rufe einen `reusable-*.yaml`-Workflow aus deinem eigenen `.github/workflows/*.yaml` auf.

    [:octicons-arrow-right-24: Workflow-Katalog](../workflows/index.md)

-   :material-robot: **Probot-Konfiguration**

    ---

    Erweitere eine geteilte `commons-*.yml` per `_extends:` ohne Workflow-Änderungen.

    [:octicons-arrow-right-24: Probot-Konfiguration](../probot/index.md)

-   :material-update: **Renovate-Preset**

    ---

    Referenziere das geteilte Preset in `renovate.json`, um Labels und Basiskonfiguration zu erben.

    [:octicons-arrow-right-24: Preset ansehen](#renovate-preset)

</div>

---

## Reusable Workflow

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  push:

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@develop
```

!!! note "Referenz-Auswahl"
    - `@develop` folgt immer dem aktuellen Stand. Empfohlen für interne Repositories, die dieses Projekt begleiten.
    - `@vX.Y.Z` pinnt auf eine veröffentlichte Version. Empfohlen, wenn Reproduzierbarkeit zählt.
    - `@master` aktualisiert sich automatisch bei jedem veröffentlichten Release und spiegelt den jeweils aktuellen Release-Tag.

---

## Probot `_extends`

```yaml title=".github/settings.yml"
_extends: gh-plumbing:.github/commons-settings.yml

repository:
  name: my-project
  description: My project description
  topics: example, demo
```

Die [Probot Settings App](https://probot.github.io/apps/settings/) löst den `_extends:`-Schlüssel auf. Lokale Schlüssel überschreiben geerbte Werte.

---

## Renovate-Preset

```json title="renovate.json"
{
  "extends": [
    "github>nolte/gh-plumbing//renovate-configs/common"
  ]
}
```

Das Preset aktiviert Pre-Commit-Updates, das Dependency-Dashboard und vergibt die Labels `chore` und `dependencies`.
