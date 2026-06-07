# Settings

Die [Probot Settings App](https://probot.github.io/apps/settings/) synchronisiert die Repository-Konfiguration aus der Versionsverwaltung.

Die geteilten Regeln umfassen:

- Default-Branch, Beschreibung, Topics, Homepage
- Issue- und PR-Funktionen (Issues, Projects, Wiki, Pages, Downloads)
- Merge-Strategien (`allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`)
- `delete_branch_on_merge`
- Branch-Protection für `master` und `develop`
- Geteilte Label-Palette

---

## Verwendung

```yaml title=".github/settings.yml"
_extends: gh-plumbing:.github/commons-settings.yml

repository:
  name: cookiecutter-gh-project
  description: Template for creating GitHub workflows and projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

!!! tip "Overrides"
    Schlüssel in der lokalen `.github/settings.yml` überschreiben die geerbten Werte. Dort nur angeben, was vom geteilten Default abweicht.

---

## Zentrale Konfiguration

```yaml title=".github/commons-settings.yml"
{%
   include "../../../.github/commons-settings.yml"
%}
```

---

## Versionierung, Drift und der `_extends`-Kontrakt

!!! warning "`_extends @<ref>` wird nicht unterstützt"
    Die Probot Settings App löst `_extends:` immer vom **Default-Branch**
    des Ziel-Repositories auf. Der Parser lehnt jeden Suffix `@<tag>`,
    `@<sha>`, `?ref=…` oder `:vN` auf dem `_extends:`-Wert komplett ab. Er
    entfernt den Suffix nicht und fährt auch nicht fort.
    Siehe [`octokit-plugin-config/src/util/extends-to-get-content-params.ts`][parser]
    — der reguläre Ausdruck verankert am Anfang und schließt `@` aus dem Dateinamen-Token aus.

    [parser]: https://github.com/probot/octokit-plugin-config/blob/main/src/util/extends-to-get-content-params.ts

**Operative Konsequenz.** Jeder Konsument hängt für seine Probot-Konfiguration
am aktuellen Stand von `gh-plumbing/develop`. Sobald sich eine `commons-*.yml`
hier ändert, driftet jeder Konsument beim nächsten Sync-Trigger — ohne Signal
zurück an den Konsumenten. Es gibt keinen reproduzierbaren Snapshot: die Frage
*„gegen welchen Stand von `commons-settings.yml` hat dieses Repository letzte
Woche synchronisiert?"* hat keine Antwort.

**Das ist ein bekannter, akzeptierter Trade-off.** Siehe Issue
[#337](https://github.com/nolte/gh-plumbing/issues/337) für die vollständige
Untersuchung (Parser-Quelltext, Alternativen-Matrix, Entscheidungsgrundlage).

### Wann dieser Trade-off blockierend wird

Drei architektonische Alternativen stehen bereit, sobald Drift load-bearing wird:

| Ansatz | Mechanismus | Pinning-Modell |
|---|---|---|
| [`github/safe-settings`](https://github.com/github/safe-settings) | Zentrales `admin`-Repository je Organisation, dreistufige Hierarchie (`org`/`suborg`/`repo`), PR-basierter Dry-Run im CI | Kein Pinning, aber eine einzige Quelle pro Organisation eliminiert repo-übergreifende `_extends`-Auflösungen |
| [`joshjohanning/bulk-github-repo-settings-sync-action`](https://github.com/marketplace/actions/bulk-github-repository-settings-sync) | GitHub Action aus einem zentralen Repository, getriggert per Cron/Push; Eingaben sind Dateipfade im aufrufenden Repository | Action-Version plus Dateiinhalt an einem bestimmten Commit ergeben einen echten Snapshot |
| `commons-*.yml` in jeden Konsumenten inlinen | Inline-Kopie in der `.github/settings.yml` des Konsumenten mit Header `# generated from gh-plumbing@<tag>`; Renovate Custom Regex Manager bumpt den Header | Snapshot pro Konsumenten-Commit; vollständiger Diff im Bump-PR |

Bis dahin gilt: **Änderungen an `commons-*.yml` sind eine Public-API-Änderung**
und werden als Breaking Change ausgerollt.

### Warum die lokale `.github/settings.yml` hier einen Propagation-Kommentar trägt

`gh-plumbing` ist Konsument seiner eigenen Commons. Die Probot App reagiert
auf Push-Events, die die **`.github/settings.yml` des Konsumenten** berühren,
nicht die obenliegende `commons-*.yml`. Um eine Commons-Änderung zu
propagieren, muss die `.github/settings.yml` dieses Repositories ebenfalls
angefasst werden (ein Kommentar-Bump genügt). Issue
[#331](https://github.com/nolte/gh-plumbing/issues/331) hält diese
Dog-Fooding-Eigenheit fest.
