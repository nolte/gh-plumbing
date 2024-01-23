
# Labelling

For Handle PR and Issue Labels use [boring-cyborg](https://probot.github.io/apps/boring-cyborg/) for setting labels by Existing roles, like changes at `./docs` always get the Label `documentations`.

## Usage

```yaml
{%
   include "../../.github/boring-cyborg.yml"
%}
```

## Labelling rules

```yaml
{%
   include "../../.github/commons-boring-cyborg.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```

## Existing labels

```yaml
{%
   include "../../.github/commons-settings.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```
The labels will be pre-configured by use the [Settings](#project-settings) GitHub Application.
