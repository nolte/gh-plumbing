# ADR-005: Consumer deklarieren ihre vollständige develop-Protection selbst

**Status:** Angenommen (2026-11-17) · **Issues:** [#442](https://github.com/nolte/gh-plumbing/issues/442), [#387](https://github.com/nolte/gh-plumbing/issues/387)

## Kontext

`commons-settings.yml` deklarierte bisher einen `develop`-Eintrag mit
`restrictions.apps` und leeren Required Contexts. Dieser Eintrag kann für keinen
Consumer dieses Portfolios stimmen, aus zwei Gründen.

Erstens akzeptiert GitHub Push-Restriktionen nur bei organisationseigenen
Repositories, und jeder Consumer gehört dem Nutzerkonto `nolte`. Die
Settings-App reicht `restrictions` unverändert durch, also scheitert die
Aktualisierung für diesen Branch mit 422. Sie überspringt nicht das eine Feld
und macht weiter.

Zweitens führt der aktuelle Quelltext der Settings-App `_extends` mit
`@fastify/deepmerge` zusammen. Diese Bibliothek ignoriert die `arrayMerge`-Option der App
und hängt Arrays aneinander. Ein `develop`-Eintrag aus den Commons landet dann
neben dem eigenen Eintrag des Consumers bei der API, beide Aktualisierungen
laufen parallel, und der letzte Schreibvorgang gewinnt. Mit `contexts: []` kann
der Commons-Eintrag die Required Checks eines Consumers löschen.

Die gehostete App verhält sich heute anders. Am 2026-11-17 fehlten dem
`develop`-Eintrag dieses Repositories `enforce_admins` und
`required_pull_request_reviews`, zwei Felder, die die API verlangt, und
trotzdem griffen seine Kontexte. Das erklärt nur ein Merge mit dem
Commons-Eintrag über `name`. Der Wettlauf ist also latent und wird real, sobald
die gehostete App den aktuellen Quelltext ausführt.

Diese Aufzeichnung beantwortet die Frage, die
[ADR-002](adr-002-branch-protection-verification.md) offen ließ, ob
`restrictions` auf `develop` etwas bringt. Nein. Bei einem nutzereigenen
Repository lehnt GitHub es mit 422 ab. Klassische Push-Restriktionen gewähren
außerdem nie einen Bypass der Required Checks. Sie schränken nur ein, wer pushen
darf. Ob die Portfolio-App beim Ausrichten der Release-Versionen auf `develop`
pushen darf, entscheiden die Branch Protection und die Rulesets von `develop`
selbst.

## Entscheidung

Den `develop`-Eintrag aus den Commons entfernen. Jeder Consumer deklariert in
seiner eigenen `.github/settings.yml` einen vollständigen `develop`-Eintrag mit
allen vier Feldern, die die API verlangt, und `restrictions: null`.

Das ergibt dasselbe Ergebnis, egal ob die App Arrays aneinanderhängt oder über
`name` zusammenführt. Für `develop` hält es Option 2 aus
[#387](https://github.com/nolte/gh-plumbing/issues/387) fest: den Default
korrigieren. Der `master`-Eintrag liegt außerhalb dieser Entscheidung und bleibt
einem Folge-Issue vorbehalten.

## Erwogene Alternativen

**Den `develop`-Eintrag behalten und `restrictions: null` setzen.** Verworfen.
Beim Aneinanderhängen bleibt der Wettlauf bestehen. Außerdem bekommt jeder
Consumer ohne eigenen Eintrag eine `develop`-Protection ohne Kontexte.

**Nur `required_status_checks` aus dem Commons-Eintrag streichen.** Verworfen.
Der verbleibende Eintrag ist ein unvollständiger Payload und scheitert mit 422.
Bei einem Merge über `name` liefert er weiterhin Felder, von denen Consumer
abhängig werden, ohne es zu merken.

**Den Merge upstream in der Settings-App korrigieren.** Übergibt die App
`mergeArray` an die Merge-Bibliothek, führt sie wieder über `name` zusammen. Das lohnt
einen Vorschlag, liegt aber nicht in der Hand dieses Portfolios.

**Das Portfolio in eine Organisation überführen.** Zurückgestellt, wie in
ADR-002.

## Folgen

Option 1 aus #387, eine Zeile `restrictions: null` in jedem Consumer, wird in
erweiterter Form zur Regel. Jeder Consumer musste seine Kontexte schon bisher
selbst deklarieren. Jetzt deklariert er den ganzen Eintrag:

```yaml title=".github/settings.yml"
branches:
  - name: develop
    protection:
      required_pull_request_reviews: null
      required_status_checks:
        strict: true
        contexts:            # die eigenen Required Checks
          - static / Static CI Tests
      enforce_admins: true
      restrictions: null
```

Consumer mit vollständigem `develop`-Eintrag merken nichts. Consumer ohne
`develop`-Eintrag haben auch bisher nichts aus den Commons erhalten, weil die
Aktualisierung mit 422 scheiterte.

Zwei Consumer haben einen unvollständigen Eintrag. `kamerplanter` lässt
`required_pull_request_reviews` weg und verließ sich darauf, dass der Merge mit
den Commons es ergänzt. Sein `develop`-Sync scheitert, bis es
`required_pull_request_reviews: null` ergänzt. `kamerplanter-android` deklariert
nur `required_status_checks` und scheiterte schon vorher, weil es
`restrictions.apps` erbte. Ein gescheiterter Sync entfernt keine bestehende
Protection, aber keine spätere Änderung greift mehr.

`scripts/branch_protection_audit.py` meldet einen `develop`-Eintrag, dem eines
der vier Felder fehlt (`null` gilt als vorhanden), und einen Branch, den sowohl
das Repository als auch die Commons deklarieren. Das wöchentliche
Portfolio-Audit zeigt beide Consumer deshalb an. Nachdem ein Consumer seinen
Eintrag geändert hat, das Ergebnis über die API prüfen, nicht über die
Einstellungsseite.

Für `master` ändert diese Aufzeichnung nichts.
[ADR-006](adr-006-consumer-owned-master-protection.md) behandelt `master`.
