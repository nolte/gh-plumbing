# ADR-006: Consumer deklarieren ihre master-Protection selbst

**Status:** Angenommen (2026-11-18) · **Issues:** [#481](https://github.com/nolte/gh-plumbing/issues/481), [#442](https://github.com/nolte/gh-plumbing/issues/442)

## Kontext

`commons-settings.yml` deklarierte bisher einen `master`-Eintrag:
`enforce_admins: true`, keine Required Checks, keine Required Reviews und
`restrictions.apps` mit `nolte-portfolio-app`. Phase 2 von
[#330](https://github.com/nolte/gh-plumbing/issues/330) hat die Restriktion
eingeführt, damit nur die Portfolio-App auf `master` pushen kann.

Der Eintrag hat bei keinem Consumer dieses Portfolios je funktioniert. GitHub
akzeptiert Push-Restriktionen nur bei organisationseigenen Repositories, und
jeder Consumer gehört dem Nutzerkonto `nolte`. Die Settings-App reicht einen
Branch-Eintrag unverändert an den Update-Endpunkt weiter, daher lehnt GitHub
die gesamte `master`-Aktualisierung mit 422 ab. Das ist derselbe Fehler, den
[ADR-005](adr-005-consumer-owned-develop-protection.md) für `develop`
beschreibt. ADR-005 hat `master` einem Folge-Issue überlassen; diese
Aufzeichnung ist dieses Folge-Issue.

Die Dokumentation behauptete, `master` sei nach Phase 2 push-restricted. Das
stimmte nicht. Der `master` dieses Repositorys ist geschützt, Admins
eingeschlossen, Force-Pushes und Löschen blockiert, aber keine Konfiguration,
die tatsächlich greift, hat diesen Zustand deklariert.

## Entscheidung

Den `master`-Eintrag aus den Commons entfernen. Die Commons deklarieren damit
überhaupt keinen `branches:`-Schlüssel mehr. Jeder Consumer, der `master`
schützen will, deklariert in seiner eigenen `.github/settings.yml` einen
vollständigen `master`-Eintrag mit allen vier Feldern, die die API verlangt,
und `restrictions: null`.

Dieses Repository deklariert seinen eigenen `master`-Eintrag mit den Werten,
die heute live sind. Ihn anzuwenden ändert daher nichts.

## Erwogene Alternativen

**Den Eintrag behalten und `restrictions: null` setzen.** Verworfen. Der
Eintrag würde dann zum ersten Mal greifen, bei allen Consumern gleichzeitig. Er
würde `enforce_admins` auf dem `master` jedes Consumers erzwingen und dessen
bestehende Protection durch die Werte der Commons ersetzen, denn die
Aktualisierung ersetzt die gesamte Protection eines Branches. Diese Änderung
hat niemand verlangt. Außerdem schreibt ein Commons-Eintrag mit dem eigenen
`master`-Eintrag eines Consumers um die Wette, wenn die App Arrays
aneinanderhängt, wie ADR-005 für `develop` erklärt.

**Den Eintrag für organisationseigene Consumer behalten.** Verworfen. Das
Portfolio hat keine, und eine geteilte Datei kann ein Feld nicht davon abhängig
machen, wem das einbindende Repository gehört. Der Eintrag würde überall, wo er
ankommt, weiter scheitern.

**Das Portfolio in eine Organisation überführen.** Zurückgestellt, wie in
[ADR-002](adr-002-branch-protection-verification.md) und ADR-005.

## Folgen

Bei keinem Consumer ändert sich die Live-Protection. Der entfernte Eintrag hat
nichts angewendet, und die Settings-App aktualisiert nur die Branches, die eine
Konfiguration aufführt. Sie entfernt keine Protection von einem Branch, den die
Konfiguration nicht mehr aufführt.

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
