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

- `prConcurrentLimit: 5`: at most five Renovate pull requests open at the same time. The cap also counts Renovate branches that have no pull request yet, because the branch limit inherits the same value.
- `prHourlyLimit: 2`: at most two new pull requests per hour. This restates the default that Renovate ships.
- `groupName: "digests"` for the `digest` and `pinDigest` update types of the `github-actions` manager: every GitHub Actions digest bump lands in one grouped pull request. Container-image digest bumps stay individual pull requests, because an image rebuild can carry a security fix without a vulnerability alert.

The reason: under branch protection with `strict: true`, every merge re-queues the full workflow fan-out of every open Renovate branch, so fewer open branches is the lever ([#439](https://github.com/nolte/gh-plumbing/issues/439)).

To pick another value, add the same key to your own `renovate.json`. The same works for the grouping rule, because Renovate appends consumer rules after the preset rules: to opt out, add a `packageRules` entry with the same `matchManagers` and `matchUpdateTypes` that sets `groupName` and `groupSlug` to `null`. Renovate merges a grouped pull request automatically only when every update in it carries `automerge: true`.

```json title="renovate.json"
{
  "extends": [
    "github>nolte/gh-plumbing//renovate-configs/common"
  ],
  "prConcurrentLimit": 10,
  "packageRules": [
    {
      "matchManagers": ["github-actions"],
      "matchUpdateTypes": ["digest", "pinDigest"],
      "groupName": null,
      "groupSlug": null
    }
  ]
}
```

!!! note "What the limits don't touch"
    - Vulnerability-alert pull requests ignore both limits, and Renovate never groups them, so a security fix never waits.
    - A lower cap doesn't close pull requests that are already open. The cap takes effect as they merge or close.
    - A consumer pinned to `#vX.Y.Z` receives these defaults with its next pin bump.
