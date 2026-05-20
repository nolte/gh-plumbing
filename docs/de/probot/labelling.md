# Labelling

Labelt PRs und Issues automatisch über [boring-cyborg](https://probot.github.io/apps/boring-cyborg/). Änderungen unter `./docs` erhalten zum Beispiel das Label `documentations`.

---

## Verwendung

```yaml title=".github/boring-cyborg.yml"
{%
   include "../../../.github/boring-cyborg.yml"
%}
```

---

## Geteilte Labelling-Regeln

```yaml title=".github/commons-boring-cyborg.yml"
{%
   include "../../../.github/commons-boring-cyborg.yml"
%}
```

---

## Label-Palette

`commons-settings.yml` deklariert die Label-Palette; die [Settings App](settings.md) wendet sie an.

```yaml
{%
   include "../../../.github/commons-settings.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```
