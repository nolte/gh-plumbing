# Probot

{%
   include-markdown "../../../README.md"
   start="<!--probot-intro-start-->"
   end="<!--probot-intro-end-->"
%}

Konsumenten referenzieren die geteilten Konfigurationen über den `_extends:`-Schlüssel:

```yaml
_extends: gh-plumbing:.github/commons-<name>.yml
```

---

## Geteilte Apps

{%
   include-markdown "../../../README.md"
   start="<!--td-probot-apps-start-->"
   end="<!--td-probot-apps-end-->"
%}

---

## Detailliert dokumentiert

<div class="grid cards" markdown>

-   :material-cog: **Settings**

    ---

    Repository-Metadaten, Branch-Protection, Labels — synchronisiert aus `commons-settings.yml`.

    [:octicons-arrow-right-24: Settings](settings.md)

-   :material-label: **Labelling**

    ---

    Labelt PRs und Issues automatisch über `boring-cyborg` per Pfad- und Titelregeln.

    [:octicons-arrow-right-24: Labelling](labelling.md)

</div>

!!! note "Release-Drafter"
    Die Seite [Workflows → Release](../workflows/release.md) dokumentiert die Release-Drafter-Probot-Konfiguration direkt neben ihrem Workflow.
