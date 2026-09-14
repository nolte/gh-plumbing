# Branch-Protection-Audit

Vergleicht die Branch-Protection, die ein Repository in `.github/settings.yml` **deklariert**, mit dem, was GitHub tatsächlich **durchsetzt**, und scheitert, wenn beides auseinanderfällt.

Der Fehler, den das Audit sucht, ist von Natur aus unsichtbar. Die Deklaration landet in der Datei, die Probot Settings App meldet nichts, und die Protection greift nie. Auffallen würde es erst bei einem Merge, der hätte blockiert werden müssen.

---

## Warum ein Skript und nicht eine Settings-Prüfung

Die Durchsetzung stammt aus **zwei unabhängigen Mechanismen**, und die Vereinigung beider entscheidet über einen Merge:

| Mechanismus | Endpunkt | Geschrieben von |
|---|---|---|
| klassische Branch-Protection | `/branches/{branch}/protection` | der Probot Settings App, aus `.github/settings.yml` |
| Repository- und Organisations-Rulesets | `/rules/branches/{branch}` | nicht von der Settings App |

Wer nur den ersten liest, meldet einen Branch als ungeschützt, während ein Ruleset ihn durchsetzt. Das Audit liest beide.

---

## Verwendung

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
    uses: nolte/gh-plumbing/.github/workflows/reusable-branch-protection-audit.yaml@<tag-oder-commit-sha>
    with:
      repos: ""
      branch: develop
      app-id: ${{ vars.PORTFOLIO_APP_ID }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
      app-private-key: ${{ secrets.PORTFOLIO_APP_PRIVATE_KEY }}
```

| Input | Default | Wirkung |
|---|---|---|
| `repos` | `""` | Leerzeichengetrennte `owner/name`-Liste. Leer erfasst jedes nicht archivierte Repository des Owners, das kein Fork ist. |
| `branch` | `develop` | Der Branch, dessen Protection verglichen wird. |
| `app-id` | `""` | Numerische App-ID. Für einen portfolio-weiten Lauf nötig, den ein einfacher `GITHUB_TOKEN` nicht leisten kann. |

!!! tip "Zeitgesteuert laufen lassen, nicht am Pull Request"
    Der Fehler ist Drift über die Zeit. Protection, die einmal griff, kann aufhören zu greifen, und kein Commit markiert den Moment. Wöchentlich genügt; ein täglicher Lauf erzieht die Leserschaft dazu, ihn zu übersehen.

---

## Das Verdikt lesen

| Status | Bedeutung |
|---|---|
| `ok` | Alles Deklarierte wird durchgesetzt, von einem der beiden Mechanismen. |
| `drift` | Ein deklarierter Kontext wird von keinem durchgesetzt. Genau dafür gibt es das Audit. |
| `unprotected` | Kontexte sind deklariert, und nichts setzt irgendetwas durch. |
| `unreadable` | Mindestens ein Endpunkt hat den Lesezugriff verweigert, ein Teil der Antwort bleibt also unbekannt. |
| `no-settings` | Das Repository hat keine `.github/settings.yml`. |

`unreadable` ist nicht `unprotected`. Ein verweigerter Lesezugriff sagt nichts über den Branch aus, und ihn als ungeschützt zu melden schickt jemanden los, um ein korrekt konfiguriertes Repository zu „reparieren".

!!! warning "Der App-Token braucht `administration: read`"
    Das Lesen klassischer Branch-Protection erfordert diese Berechtigung, der Ruleset-Endpunkt nicht. Eine App, die nur Letzteres hat, meldet `unreadable`, zählt die Ruleset-Kontexte mit und lässt die klassische Hälfte unbekannt — korrekt, aber nur die halbe Antwort. Siehe [Issue #387](https://github.com/nolte/gh-plumbing/issues/387).

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-branch-protection-audit.yaml"
{%
   include "../../../.github/workflows/reusable-branch-protection-audit.yaml"
%}
```
