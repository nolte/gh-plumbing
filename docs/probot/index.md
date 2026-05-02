# Probot

{%
   include-markdown "../../README.md"
   start="<!--probot-intro-start-->"
   end="<!--probot-intro-end-->"
%}

Consumers reference the shared configurations via the `_extends:` key:

```yaml
_extends: gh-plumbing:.github/commons-<name>.yml
```

---

## Shared apps

{%
   include-markdown "../../README.md"
   start="<!--td-probot-apps-start-->"
   end="<!--td-probot-apps-end-->"
%}

---

## Documented in detail

<div class="grid cards" markdown>

-   :material-cog: **Settings**

    ---

    Repository metadata, branch protection, labels—synced from `commons-settings.yml`.

    [:octicons-arrow-right-24: Settings](settings.md)

-   :material-label: **Labelling**

    ---

    Automatically labels PRs and issues via `boring-cyborg` using path and title rules.

    [:octicons-arrow-right-24: Labelling](labelling.md)

</div>

!!! note "Release drafter"
    The [Workflows → Release](../workflows/release.md) page documents the release-drafter Probot configuration next to its workflow.
