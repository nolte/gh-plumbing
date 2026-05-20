# Überblick

{%
   include-markdown "../../README.md"
   start="<!--intro-start-->"
   end="<!--intro-end-->"
%}

---

## Inhalt

<div class="grid cards" markdown>

-   :material-rocket-launch: **Erste Schritte**

    ---

    Wie nachgelagerte Repositories die wiederverwendbaren Workflows und die geteilte Probot-Konfiguration einbinden.

    [:octicons-arrow-right-24: Hier starten](getting-started/index.md)

-   :material-cog-sync: **Workflows**

    ---

    Wiederverwendbare GitHub-Actions-Workflows für statische Tests, Dokumentation und Releases.

    [:octicons-arrow-right-24: Workflow-Katalog](workflows/index.md)

-   :material-robot: **Probot**

    ---

    Geteilte Probot-Konfigurationen, eingebunden per `_extends:` für Settings, Labelling und Release-Notes.

    [:octicons-arrow-right-24: Probot-Konfigurationen](probot/index.md)

-   :material-key-variant: **Portfolio-App**

    ---

    Zentrale GitHub App, die die `GITHUB_TOKEN`-Cascade-Lücke schließt. Funktioniert für Organisationen und persönliche Accounts; Terraform-Modul inklusive.

    [:octicons-arrow-right-24: Setup](portfolio-app/setup.md)

-   :material-wrench: **Entwicklung**

    ---

    Lokale Entwicklungsumgebung: `asdf`, `task`, `pre-commit` und Workflows mit `act` ausführen.

    [:octicons-arrow-right-24: Mitwirken](development/index.md)

</div>

---

## Wie Konsumenten dieses Repository referenzieren

=== "Reusable workflow"

    ```yaml
    jobs:
      static:
        uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@develop
    ```

=== "Probot `_extends`"

    ```yaml
    # .github/settings.yml
    _extends: gh-plumbing:.github/commons-settings.yml
    ```

=== "Renovate-Preset"

    ```json
    {
      "extends": ["github>nolte/gh-plumbing//renovate-configs/common"]
    }
    ```

!!! tip "Pinning-Strategie"
    - **Wiederverwendbare Workflows:** `@develop` für den aktuellen Stand, `@vX.Y.Z` für Reproduzierbarkeit, `@master` für den jeweils zuletzt veröffentlichten Release.
    - **Probot `_extends`:** kein Pin möglich — wird immer vom Default-Branch (`develop`) aufgelöst. Siehe [Probot → Settings → Versionierung](probot/settings.md#versionierung-drift-und-der-_extends-kontrakt).
    - **Renovate-Preset:** mit `#vX.Y.Z` (Achtung: `#`, nicht `@`) an einen Release-Tag pinnen.
