# Overview

{%
   include-markdown "../../README.md"
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

    Shared Probot configurations consumed via `_extends:` for settings, labelling, and release notes.

    [:octicons-arrow-right-24: Probot configurations](probot/index.md)

-   :material-key-variant: **Portfolio App**

    ---

    Centralised GitHub App that closes the `GITHUB_TOKEN` cascade gap. Works for organisations and personal accounts. Terraform module included.

    [:octicons-arrow-right-24: Setup](portfolio-app/setup.md)

-   :material-wrench: **Development**

    ---

    Local development setup: `asdf`, `task`, `pre-commit`, and running workflows with `act`.

    [:octicons-arrow-right-24: Contribute](development/index.md)

</div>

---

## How consumers reference this repository

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
    - **Reusable workflows:** `@develop` for latest, `@vX.Y.Z` for reproducibility, `@master` for the latest published release.
    - **Probot `_extends`:** no pin possible—always resolves from the default branch (`develop`). See [Probot → Settings → Versioning](probot/settings.md#versioning-drift-and-the-_extends-contract).
    - **Renovate preset:** append `#vX.Y.Z` (note: `#`, not `@`) to pin to a release tag.
