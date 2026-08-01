# Workflows

Reusable GitHub Actions workflows live under `.github/workflows/reusable-*.y{a}ml`. Consumers reference them via:

```yaml
uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@<tag>
```

!!! warning "Replace `<tag>` with a release tag, never `@develop`"

    `<tag>` is a placeholder on purpose. Pick a version from the
    [releases page](https://github.com/nolte/gh-plumbing/releases), for example
    `@v1.1.26`, and let Renovate propose the bumps.

    These pages previously showed `@develop`, so consumers that followed them
    ended up unpinned *because* they followed the documentation. A branch
    reference resolves to whatever that branch points at when your workflow
    runs, so a change here reaches your CI immediately and without review.

    This repository's own wrapper workflows still use `@develop`. That is
    deliberate dog-fooding of the unreleased state, is
    [tracked separately](https://github.com/nolte/gh-plumbing/issues/392), and
    is not a pattern to copy.

---

## Catalog

{%
   include-markdown "../../../README.md"
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

-   :material-chart-box-outline: **Coverage**

    ---

    Render Python or Node.js test coverage into the job summary, with an optional `fail-under` gate.

    [:octicons-arrow-right-24: Coverage workflows](coverage.md)

-   :material-book-open-variant: **Documentation**

    ---

    Build and publish an mkdocs site to GitHub Pages.

    [:octicons-arrow-right-24: reusable-mkdocs](documentation.md)

-   :material-tag: **Release**

    ---

    Draft release notes and refresh `master` to the latest release tag.

    [:octicons-arrow-right-24: Release workflows](release.md)

-   :material-home-assistant: **HACS validation**

    ---

    Validate a HACS custom integration with `hacs/action` and `hassfest`, and ship the release ZIP asset.

    [:octicons-arrow-right-24: HACS validation](hacs.md)

</div>

!!! info "Conventions"
    Every reusable workflow accepts its inputs via `workflow_call.inputs`. Callers pass secrets explicitly—this repository never reads ambient organization secrets.
