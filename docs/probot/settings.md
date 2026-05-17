# Settings

The [Probot Settings App](https://probot.github.io/apps/settings/) syncs repository configuration from version control.

Shared rules cover:

- Default branch, description, topics, homepage
- Issue/PR features (issues, projects, wiki, pages, downloads)
- Merge strategies (`allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`)
- `delete_branch_on_merge`
- Branch protection for `master` and `develop`
- Shared label palette

---

## Usage

```yaml title=".github/settings.yml"
_extends: gh-plumbing:.github/commons-settings.yml

repository:
  name: cookiecutter-gh-project
  description: Template for creating GitHub workflows and projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

!!! tip "Overrides"
    Keys in your local `.github/settings.yml` override the inherited values. Only specify what differs from the shared defaults.

---

## Central configuration

```yaml title=".github/commons-settings.yml"
{%
   include "../../.github/commons-settings.yml"
%}
```

---

## Versioning, drift, and the `_extends` contract

!!! warning "`_extends @<ref>` isn't supported"
    The Probot Settings App always resolves `_extends:` against the **default
    branch** of the target repository. The parser rejects any `@<tag>`,
    `@<sha>`, `?ref=…`, or `:vN` suffix on the `_extends:` value outright; it
    doesn't strip the suffix and continue.
    See [`octokit-plugin-config/src/util/extends-to-get-content-params.ts`][parser]
    — the regex anchors at the start and excludes `@` from the filename token.

    [parser]: https://github.com/probot/octokit-plugin-config/blob/main/src/util/extends-to-get-content-params.ts

**Operational consequence.** Every consumer lives at the tip of
`gh-plumbing/develop` for its Probot configuration. Whenever a
`commons-*.yml` file changes here, every consumer drifts on its next sync
trigger, with no signal back to the consumer. There is no reproducible
snapshot: *"which `commons-settings.yml` state did this repository sync
against last week?"* has no answer.

**This is a known, accepted trade-off.** See issue
[#337](https://github.com/nolte/gh-plumbing/issues/337) for the full
investigation (parser source, alternatives matrix, decision rationale).

### When this trade-off becomes blocking

Three architectural alternatives are available the day drift turns load-bearing:

| Approach | Mechanism | Pinning model |
|---|---|---|
| [`github/safe-settings`](https://github.com/github/safe-settings) | Central `admin` repository per org, three-level hierarchy (`org`/`suborg`/`repo`), PR-based dry-run CI | No pinning, but a single source per org eliminates cross-repository `_extends` resolves |
| [`joshjohanning/bulk-github-repo-settings-sync-action`](https://github.com/marketplace/actions/bulk-github-repository-settings-sync) | GitHub Action invoked from a central repository on cron/push; inputs are file paths in the calling repository | Action version plus file content at a specific commit, giving a true snapshot |
| Inline `commons-*.yml` into each consumer | Inline copy in each consumer's `.github/settings.yml` with a `# generated from gh-plumbing@<tag>` header; Renovate Custom Regex Manager bumps the header | Snapshot per consumer commit; full diff in the bump PR |

Until then, treat **edits to `commons-*.yml` as a public API change** and
roll them out as breaking changes.

### Why the local `.github/settings.yml` here carries a propagation comment

`gh-plumbing` is itself a consumer of its own commons. The Probot App reacts
to push events that touch the **consumer's** `.github/settings.yml`, not the
upstream `commons-*.yml`. To propagate a commons change, touch this
repository's `.github/settings.yml` as well (a comment bump is enough). Issue
[#331](https://github.com/nolte/gh-plumbing/issues/331) tracks this
dog-fooding quirk.
