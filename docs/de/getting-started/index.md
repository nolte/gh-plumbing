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
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
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

### Pull-Request-Volumen

Das Preset begrenzt außerdem, wie viele Renovate-Pull-Requests ein Consumer gleichzeitig offen hält:

- `prConcurrentLimit: 5`: höchstens fünf offene Renovate-Pull-Requests gleichzeitig.
- `prHourlyLimit: 2`: höchstens zwei neue Pull-Requests pro Stunde. Das entspricht Renovates eigenem Standardwert.
- `groupName: "digests"` für die Update-Typen `digest` und `pinDigest`: alle Digest-Bumps landen in einem gemeinsamen Pull-Request.

Der Grund: Unter Branch-Protection mit `strict: true` stellt jeder Merge den kompletten Workflow-Fan-out jedes offenen Renovate-Branches neu in die Warteschlange. Weniger offene Branches sind daher der Hebel ([#439](https://github.com/nolte/gh-plumbing/issues/439)).

Einen anderen Wert setzt du über denselben Schlüssel in deiner eigenen `renovate.json`. Für die Gruppierungsregel gilt dasselbe: Ein `packageRules`-Eintrag mit denselben `matchUpdateTypes` und einem anderen `groupName` gewinnt, weil Renovate Consumer-Regeln hinter die Regeln des Presets hängt.

```json title="renovate.json"
{
  "extends": [
    "github>nolte/gh-plumbing//renovate-configs/common"
  ],
  "prConcurrentLimit": 10
}
```

!!! note "Was die Limits nicht berühren"
    - Pull-Requests aus Vulnerability-Alerts ignorieren beide Limits, und Renovate gruppiert sie nie. Ein Security-Fix wartet also nicht.
    - Ein niedrigeres Limit schließt keine bereits offenen Pull-Requests. Es greift, sobald diese gemergt oder geschlossen werden.
    - Ein Consumer, der das Preset auf `#vX.Y.Z` pinnt, erhält die neuen Standardwerte erst mit dem nächsten Pin-Bump.
