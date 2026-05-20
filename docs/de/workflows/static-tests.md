# Statische Tests

Führt ein minimales Bündel statischer Analyse bei jedem Push aus und liefert schnelles Feedback ohne externe Dienste.

- [`pre-commit/action`](https://github.com/pre-commit/action) führt die in `.pre-commit-config.yaml` definierten Hooks aus
- [`zbeekman/EditorConfig-Action`](https://github.com/zbeekman/EditorConfig-Action) prüft `.editorconfig`-Regeln

---

## Verwendung

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  push:

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@develop
```

!!! tip "Erforderlicher Status-Check"
    Kombiniere den Workflow mit einer Branch-Protection-Regel, die den Check `static / Static CI Tests` verlangt — siehe [Settings](../probot/settings.md).

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../../.github/workflows/reusable-pre-commit.yaml"
%}
```
