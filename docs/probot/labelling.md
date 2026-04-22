# Labelling

Auto-labels PRs and issues using [boring-cyborg](https://probot.github.io/apps/boring-cyborg/). Changes under `./docs`, for example, automatically receive the `documentations` label.

---

## Usage

```yaml title=".github/boring-cyborg.yml"
{%
   include "../../.github/boring-cyborg.yml"
%}
```

---

## Shared labelling rules

```yaml title=".github/commons-boring-cyborg.yml"
{%
   include "../../.github/commons-boring-cyborg.yml"
%}
```

---

## Label palette

`commons-settings.yml` declares the label palette; the [Settings App](settings.md) applies it.

```yaml
{%
   include "../../.github/commons-settings.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```
