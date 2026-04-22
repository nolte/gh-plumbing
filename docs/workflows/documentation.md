# Documentation

Builds an [mkdocs](https://www.mkdocs.org/) site and publishes it to GitHub Pages.

This workflow is part of the [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project) template.

---

## Usage

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
    Ensure `has_pages: true` is set on the target repo. The shared Probot settings already include this — see [Settings](../probot/settings.md).

---

## Central configuration

```yaml title=".github/workflows/reusable-mkdocs.yaml"
{%
   include "../../.github/workflows/reusable-mkdocs.yaml"
%}
```
