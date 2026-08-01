# Workflows

Wiederverwendbare GitHub-Actions-Workflows liegen unter `.github/workflows/reusable-*.y{a}ml`. Konsumenten referenzieren sie über:

```yaml
uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>
```

!!! warning "`<tag>` durch einen Release-Tag ersetzen, niemals `@develop`"

    `<tag>` ist bewusst ein Platzhalter. Wähle eine Version auf der
    [Releases-Seite](https://github.com/nolte/gh-plumbing/releases), zum
    Beispiel `@v1.1.26`, und lass Renovate die Bumps vorschlagen.

    Diese Seiten zeigten früher `@develop`. Konsumenten, die der Dokumentation
    folgten, waren also *deshalb* ungepinnt. Eine Branch-Referenz löst auf das
    auf, worauf der Branch zur Laufzeit zeigt — eine Änderung hier erreicht
    deine CI sofort und ungeprüft.

    Die Wrapper-Workflows dieses Repositories nutzen weiterhin `@develop`. Das
    ist bewusstes Dogfooding des unveröffentlichten Stands, wird
    [separat verfolgt](https://github.com/nolte/gh-plumbing/issues/392) und ist
    kein Muster zum Nachbauen.

---

## Katalog

{%
   include-markdown "../../../README.md"
   start="<!--td-workflows-start-->"
   end="<!--td-workflows-end-->"
%}

---

## Detailliert dokumentiert

<div class="grid cards" markdown>

-   :material-check-all: **Statische Tests**

    ---

    Pre-Commit- und EditorConfig-Linting für jedes Repository.

    [:octicons-arrow-right-24: reusable-pre-commit](static-tests.md)

-   :material-chart-box-outline: **Coverage**

    ---

    Python- oder Node.js-Testabdeckung in die Job-Zusammenfassung rendern, mit optionalem `fail-under`-Gate.

    [:octicons-arrow-right-24: Coverage-Workflows](coverage.md)

-   :material-book-open-variant: **Dokumentation**

    ---

    Eine MkDocs-Site bauen und auf GitHub Pages veröffentlichen.

    [:octicons-arrow-right-24: reusable-mkdocs](documentation.md)

-   :material-tag: **Release**

    ---

    Release-Notes als Entwurf pflegen und `master` auf den aktuellen Release-Tag bringen.

    [:octicons-arrow-right-24: Release-Workflows](release.md)

-   :material-home-assistant: **HACS-Validierung**

    ---

    Eine HACS-Custom-Integration mit `hacs/action` und `hassfest` validieren und das Release-ZIP-Asset ausliefern.

    [:octicons-arrow-right-24: HACS-Validierung](hacs.md)

</div>

!!! info "Konventionen"
    Jeder wiederverwendbare Workflow nimmt seine Eingaben über `workflow_call.inputs` entgegen. Aufrufer übergeben Secrets explizit — dieses Repository liest keine umgebungsweiten Organisation-Secrets.
