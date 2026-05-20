# Dokumentation

Baut eine [mkdocs](https://www.mkdocs.org/)-Site und veröffentlicht sie auf GitHub Pages.

Dieser Workflow ist Teil des Templates [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project).

---

## Verwendung

```yaml title=".github/workflows/release-cd-deliver-docs.yml"
on:
  push:
    branches:
      - develop

jobs:
  deliver_docs:
    uses: nolte/gh-plumbing/.github/workflows/reusable-mkdocs.yaml@develop
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
```

!!! note "GitHub Pages"
    Das Ziel-Repository muss `has_pages: true` deklarieren. Die geteilten Probot-Settings enthalten das bereits — siehe [Settings](../probot/settings.md).

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-mkdocs.yaml"
{%
   include "../../../.github/workflows/reusable-mkdocs.yaml"
%}
```
