# Branch-protection audit

Compares the branch protection a repository **declares** in `.github/settings.yml` against what GitHub **enforces**, and fails when the two disagree.

The fault it looks for is invisible by design. A declaration lands in the file, the Probot Settings App reports nothing, and the protection never applies. Nobody notices until a merge that should have been blocked goes through.

---

## Why a script rather than a settings check

Enforcement comes from **two independent mechanisms**, and the union of both gates a merge:

| Mechanism | Endpoint | Written by |
|---|---|---|
| classic branch protection | `/branches/{branch}/protection` | the Probot Settings App, from `.github/settings.yml` |
| repository and organisation rulesets | `/rules/branches/{branch}` | not the Settings App |

Reading only the first reports a branch as unprotected while a ruleset enforces it. The audit reads both.

---

## Usage

```yaml title=".github/workflows/portfolio-branch-protection-audit.yml"
on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: read

jobs:
  audit:
    permissions:
      contents: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-branch-protection-audit.yaml@<tag-or-commit-sha>
    with:
      repos: ""
      branch: develop
      app-id: ${{ vars.PORTFOLIO_APP_ID }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
      app-private-key: ${{ secrets.PORTFOLIO_APP_PRIVATE_KEY }}
```

| Input | Default | Effect |
|---|---|---|
| `repos` | `""` | Space-separated `owner/name` list. Empty surveys every non-archived, non-fork repository of the owner. |
| `branch` | `develop` | The branch whose protection the audit compares. |
| `app-id` | `""` | Numeric App ID. Set it to read across a portfolio, which a plain `GITHUB_TOKEN` can't do. |

!!! tip "Run it on a schedule, not on a pull request"
    The fault is drift over time. Protection that applied once can stop applying, and no commit marks the moment it does. Weekly is enough, and a daily run teaches the reader to ignore it.

---

## Reading the verdict

| Status | Meaning |
|---|---|
| `ok` | Everything declared is enforced, by either mechanism. |
| `drift` | A declared context is enforced by neither. This is the finding the audit exists for. |
| `unprotected` | Contexts are declared and nothing enforces anything. |
| `unreadable` | At least one endpoint refused the read, so part of the answer is unknown. |
| `no-settings` | The repository has no `.github/settings.yml`. |

`unreadable` isn't `unprotected`. A refused read tells you nothing about the branch, and reporting it as unprotected would send somebody to "fix" a repository that's correctly configured.

!!! warning "The App token needs `administration: read`"
    Reading classic branch protection requires that permission. The ruleset endpoint doesn't. An App holding only the latter reports `unreadable` with the ruleset contexts counted and the classic half unknown—accurate, but only half an answer. See [issue #387](https://github.com/nolte/gh-plumbing/issues/387).

---

## Central configuration

```yaml title=".github/workflows/reusable-branch-protection-audit.yaml"
{%
   include "../../../.github/workflows/reusable-branch-protection-audit.yaml"
%}
```
