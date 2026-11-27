# ADR-006: Consumer deklarieren ihre master-Protection selbst

**Status:** Angenommen (2026-11-18) · **Issues:** [#481](https://github.com/nolte/gh-plumbing/issues/481), [#442](https://github.com/nolte/gh-plumbing/issues/442)

## Kontext

`commons-settings.yml` deklarierte bisher einen `master`-Eintrag:
`enforce_admins: true`, keine Required Checks, keine Required Reviews. Von
2020 bis Mai 2026 trug der Eintrag `restrictions: null`. In dieser Form konnte
er greifen, und die zwei Consumer, die einen `master`-Branch haben, dieses
Repository und `esphome-configs`, tragen heute genau diese Protection.

Phase 2 von [#330](https://github.com/nolte/gh-plumbing/issues/330) hat
`restrictions: null` durch `restrictions.apps` mit `nolte-portfolio-app`
ersetzt ([#355](https://github.com/nolte/gh-plumbing/pull/355)), damit nur die
Portfolio-App auf `master` pushen kann. GitHub akzeptiert Push-Restriktionen
nur bei organisationseigenen Repositories, und jeder Consumer gehört dem
Nutzerkonto `nolte`. Die Settings-App reicht einen Branch-Eintrag unverändert
an den Update-Endpunkt weiter. In dieser Form lehnt GitHub die gesamte
`master`-Aktualisierung ab, wie zuvor bei `develop`
([#416](https://github.com/nolte/gh-plumbing/issues/416),
[ADR-005](adr-005-consumer-owned-develop-protection.md)). Für `master` selbst
hat niemand die Ablehnung festgehalten; diese Aufzeichnung stützt sich auf die
von GitHub dokumentierte Grenze und auf den Fall `develop`. ADR-005 hat
`master` einem Folge-Issue überlassen; diese Aufzeichnung ist dieses
Folge-Issue.

Die Dokumentation behauptete, `master` sei nach Phase 2 push-restricted. Das
stimmte nicht. Der `master` dieses Repositorys trägt weiterhin die Protection
aus der Zeit vor Phase 2, aber seit Phase 2 hat keine Konfiguration, die
tatsächlich greift, sie deklariert.

## Entscheidung

Den `master`-Eintrag aus den Commons entfernen. Die Commons deklarieren damit
überhaupt keinen `branches:`-Schlüssel mehr. Jeder Consumer, der `master`
schützen will, deklariert in seiner eigenen `.github/settings.yml` einen
vollständigen `master`-Eintrag mit allen vier Feldern, die die API verlangt,
und `restrictions: null`.

Dieses Repository deklariert seinen eigenen `master`-Eintrag mit den Werten,
die heute live sind. Ihn anzuwenden ändert daher nichts.

## Erwogene Alternativen

**Den Eintrag behalten und `restrictions: null` setzen.** Verworfen, obwohl es
funktionieren würde: Es stellt die Form wieder her, die der Eintrag bis Mai
2026 hatte, und ändert bei den zwei Consumern mit `master`-Branch live nichts.
Drei Gründe sprechen dagegen. Ein Commons-Eintrag schreibt mit dem eigenen
`master`-Eintrag eines Consumers um die Wette, wenn die App Arrays
aneinanderhängt, wie ADR-005 für `develop` erklärt. Die meisten Consumer haben
keinen `master`-Branch, die Commons würden ihnen also eine Aktualisierung für
einen Branch schicken, den es nicht gibt. Und eine Regel hält sich leichter
als zwei: Seit ADR-005 gehört einem Consumer seine `develop`-Protection, jetzt
gehört ihm jeder Branch.

**Den Eintrag für organisationseigene Consumer behalten.** Verworfen. Das
Portfolio hat keine, und eine geteilte Datei kann ein Feld nicht davon abhängig
machen, wem das einbindende Repository gehört. Der Eintrag würde überall, wo er
ankommt, weiter scheitern.

**Das Portfolio in eine Organisation überführen.** Zurückgestellt, wie in
[ADR-002](adr-002-branch-protection-verification.md) und ADR-005.

## Folgen

Bei keinem Consumer ändert sich die Live-Protection. Die Settings-App
aktualisiert nur die Branches, die eine Konfiguration aufführt. Sie entfernt
keine Protection von einem Branch, den die Konfiguration nicht mehr aufführt.
Das folgt aus dem Quellcode der App, `lib/plugins/branches.js`; an der
gehosteten App wurde es nicht beobachtet.

Derselbe Quellcode zeigt eine Nebenwirkung. Die App baut jede
Branch-Aktualisierung auf der vorherigen auf, ein Eintrag ohne ein Pflichtfeld
erbt es also vom Eintrag davor. Ein Consumer, dessen `develop`-Eintrag
`required_pull_request_reviews` weglässt, bekam das Feld bisher vom
`master`-Eintrag der Commons. Ohne ihn lehnt GitHub im nächsten Settings-Sync
dieses Consumers die Aktualisierung der `develop`-Protection ab, bis sein
Eintrag vollständig ist. Repository-Einstellungen und Labels aus demselben Sync
greifen weiterhin. `kamerplanter` ist der
bekannte Fall; ADR-005 nennt das fehlende Feld bereits.

Ein Consumer, der `master` schützen will, deklariert den ganzen Eintrag:

```yaml title=".github/settings.yml"
branches:
  - name: master
    protection:
      required_pull_request_reviews: null
      required_status_checks: null
      enforce_admins: true
      restrictions: null
```

Die Aktualisierung ersetzt die gesamte Protection des Branches. Felder, die der
Eintrag weglässt, etwa `allow_force_pushes` und `allow_deletions`, erhalten den
API-Default `false`. Ein Consumer, dessen `master` einen anderen Wert braucht,
muss ihn deklarieren. Ein organisationseigener Consumer, bei dem nur die App
pushen soll, deklariert `restrictions.apps` in seinem eigenen Eintrag.

`reusable-release-cd-refresh-master.yml` liest Protection und Rulesets des
Ziels und wählt daraus seine Schreibstrategie
([ADR-001](adr-001-presentation-branch-reset.md)). Nichts davon ändert sich,
der Workflow verhält sich also wie bisher. Wo der `GITHUB_TOKEN`-Fallback
bisher auf `master` pushen konnte, kann er es weiterhin.

Ein Test in `scripts/tests/test_required_check_triggers.py` schlägt fehl, wenn
ein Commons-Branch-Eintrag mit `restrictions` zurückkommt. Nachdem ein Consumer
seinen Eintrag geändert hat, das Ergebnis über die API prüfen, nicht über die
Einstellungsseite.
