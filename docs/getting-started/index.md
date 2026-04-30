# Getting started

`gh-plumbing` exposes three integration surfaces. Pick the one that matches the change you want in your target repository.

---

## Choose your integration

<div class="grid cards" markdown>

-   :material-cog-sync: **Reusable workflow**

    ---

    Call a `reusable-*.yaml` workflow from your own `.github/workflows/*.yaml`.

    [:octicons-arrow-right-24: Workflow catalog](../workflows/index.md)

-   :material-robot: **Probot configuration**

    ---

    Extend a shared `commons-*.yml` via `_extends:` without workflow changes.

    [:octicons-arrow-right-24: Probot configuration](../probot/index.md)

-   :material-update: **Renovate preset**

    ---

    Reference the shared preset in `renovate.json` to inherit labels and base configuration.

    [:octicons-arrow-right-24: See preset](#renovate-preset)

</div>

---

## Reusable workflow

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  push:

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@develop
```

!!! note "Reference selection"
    - `@develop` always tracks the latest changes; recommended for internal repositories that follow this project closely.
    - `@vX.Y.Z` pins to a released version; recommended when you need reproducibility.
    - `master` refreshes automatically on every published release and mirrors the latest release tag.

---

## Probot `_extends`

```yaml title=".github/settings.yml"
_extends: gh-plumbing:.github/commons-settings.yml

repository:
  name: my-project
  description: My project description
  topics: example, demo
```

The [Probot Settings App](https://probot.github.io/apps/settings/) resolves the `_extends:` key. Local keys override inherited values.

---

## Renovate preset

```json title="renovate.json"
{
  "extends": [
    "github>nolte/gh-plumbing//renovate-configs/common"
  ]
}
```

The preset enables pre-commit updates, the dependency dashboard, and applies the `chore` + `dependencies` labels.
