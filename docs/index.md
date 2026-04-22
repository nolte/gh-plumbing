# GitHub Plumbing

{%
   include-markdown "../README.md"
   start="<!--intro-start-->"
   end="<!--intro-end-->"
%}

---

## What's inside

<div class="grid cards" markdown>

-   :material-rocket-launch: **Getting started**

    ---

    How downstream repositories consume the reusable workflows and shared Probot configuration.

    [:octicons-arrow-right-24: Start here](getting-started/index.md)

-   :material-cog-sync: **Workflows**

    ---

    Reusable GitHub Actions workflows for static tests, documentation, and releases.

    [:octicons-arrow-right-24: Workflow catalog](workflows/index.md)

-   :material-robot: **Probot**

    ---

    Shared Probot configurations consumed via `_extends:` — settings, labelling, release notes.

    [:octicons-arrow-right-24: Probot configs](probot/index.md)

-   :material-wrench: **Development**

    ---

    Local development setup: `asdf`, `task`, `pre-commit`, and running workflows with `act`.

    [:octicons-arrow-right-24: Contribute](development/index.md)

</div>

---

## How consumers reference this repo

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

=== "Renovate preset"

    ```json
    {
      "extends": ["github>nolte/gh-plumbing//renovate-configs/common"]
    }
    ```

!!! tip "Pinning strategy"
    Reference `@develop` for the latest changes or pin to a release tag (for example `@v1.1.8`) for stability. The `master` branch is auto-refreshed on every published release.
