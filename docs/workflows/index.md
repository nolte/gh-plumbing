# Workflows

Reusable GitHub Actions workflows live under `.github/workflows/reusable-*.y{a}ml`. Consumers reference them via:

```yaml
uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@develop
```

---

## Catalog

{%
   include-markdown "../../README.md"
   start="<!--td-workflows-start-->"
   end="<!--td-workflows-end-->"
%}

---

## Documented in detail

<div class="grid cards" markdown>

-   :material-check-all: **Static tests**

    ---

    Pre-commit + EditorConfig linting for any repository.

    [:octicons-arrow-right-24: reusable-pre-commit](static-tests.md)

-   :material-book-open-variant: **Documentation**

    ---

    Build and publish an mkdocs site to GitHub Pages.

    [:octicons-arrow-right-24: reusable-mkdocs](documentation.md)

-   :material-tag: **Release**

    ---

    Draft release notes and refresh `master` to the latest release tag.

    [:octicons-arrow-right-24: Release workflows](release.md)

</div>

!!! info "Conventions"
    Every reusable workflow accepts its inputs via `workflow_call.inputs`. Callers pass secrets explicitly—this repository never reads ambient organization secrets.
