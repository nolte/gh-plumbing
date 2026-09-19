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
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
```

!!! note "Reference selection"
    - `@develop` always tracks the latest changes. Recommended for internal repositories that follow this project.
    - `@vX.Y.Z` pins to a released version. Recommended when you need reproducibility.
    - `@master` refreshes automatically on every published release and mirrors the latest release tag.

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

### Pull request volume

The preset also bounds how many Renovate pull requests a consumer carries:

- `prConcurrentLimit: 5`: at most five Renovate pull requests open at the same time.
- `prHourlyLimit: 2`: at most two new pull requests per hour. This restates the default that Renovate ships.
- `groupName: "digests"` for the `digest` and `pinDigest` update types: every digest bump lands in one grouped pull request.

The reason: under branch protection with `strict: true`, every merge re-queues the full workflow fan-out of every open Renovate branch, so fewer open branches is the lever ([#439](https://github.com/nolte/gh-plumbing/issues/439)).

To pick another value, add the same key to your own `renovate.json`. The same works for the grouping rule: a `packageRules` entry with the same `matchUpdateTypes` and another `groupName` wins, because Renovate appends consumer rules after the preset rules.

```json title="renovate.json"
{
  "extends": [
    "github>nolte/gh-plumbing//renovate-configs/common"
  ],
  "prConcurrentLimit": 10
}
```

!!! note "What the limits don't touch"
    - Vulnerability-alert pull requests ignore both limits, and Renovate never groups them, so a security fix never waits.
    - A lower cap doesn't close pull requests that are already open. The cap takes effect as they merge or close.
    - A consumer pinned to `#vX.Y.Z` receives these defaults with its next pin bump.
