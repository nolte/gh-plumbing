# HACS-Validierung

Validiert eine über HACS verteilte Home-Assistant-Custom-Integration mit den beiden offiziellen Actions, sodass ein konsumierendes Repository dasselbe Gate erbt, das HACS und Home Assistant Core anwenden.

- [`hacs/action`](https://github.com/hacs/action) führt denselben Code aus, den HACS zur Validierung eines Repositories nutzt (Existenz von `hacs.json`, Brands, Topics, …); `category` ist standardmäßig `integration`
- [`home-assistant/actions/hassfest`](https://github.com/home-assistant/actions) validiert das Integrations-Manifest und die Struktur, auch für Custom Integrations

---

## Verwendung

```yaml title=".github/workflows/ci.yml"
on:
  push:
  pull_request:

jobs:
  hacs-validate:
    uses: nolte/gh-plumbing/.github/workflows/reusable-hacs-validate.yaml@develop
```

!!! tip "Custom-Repository vs. Default-Store"
    Lasse `ignore` leer für einen Default-Store-tauglichen Lauf — HACS verbietet ignorierte Checks für die Default-Store-Aufnahme. Ein reines Custom-Repository darf nicht erfüllbare Checks ignorieren, z. B. `with: { ignore: "brands" }`.

---

## Release-ZIP-Asset

Für HACS-Integrationen baut [`reusable-release-publish.yml`](release.md) ein `<domain>.zip`-Asset aus `custom_components/<domain>/` am Ziel-Commit des Release und hängt es **vor** dem Umschalten auf `draft=false` an den Draft — so sieht HACS nie ein Release ohne seinen Download. Das geschieht automatisch, sobald das Repository eine `custom_components/<domain>/manifest.json` trägt; es ist keine zusätzliche Verdrahtung nötig.

Der vollständige Release-und-Distributions-Kontrakt ist in [`spec/ha/hacs-release`](https://github.com/nolte/claude-home-assistant/blob/develop/spec/ha/hacs-release/de.md) in `claude-home-assistant` spezifiziert.

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-hacs-validate.yaml"
{%
   include "../../../.github/workflows/reusable-hacs-validate.yaml"
%}
```
