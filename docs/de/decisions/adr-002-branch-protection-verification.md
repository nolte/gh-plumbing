# ADR-002: Branch Protection prüfen, bevor die Defaults geändert werden

**Status:** Angenommen (2026-08-01) · **Issue:** [#387](https://github.com/nolte/gh-plumbing/issues/387)

## Kontext

In `.github/settings.yml` deklarierte Branch Protection wird häufig nicht
angewendet. Die Deklaration sieht korrekt aus, die Probot-Settings-App meldet
nichts, und der Schutz fehlt. Eine Erhebung über neun Consumer am 2026-07-26 fand
fünf mit Drift, in mindestens drei verschiedenen Ausprägungen.

Eine Ursache ist bestätigt. Die Commons deklarieren `restrictions.apps` für
`develop` und `master`. GitHub akzeptiert Push-Restriktionen nur bei
organisationseigenen Repositories, und `nolte` ist ein Nutzerkonto. Die
Settings-App verwirft daraufhin die gesamte Protection-Aktualisierung, statt nur
das eine nicht unterstützte Feld zu überspringen.

Diese Ursache erklärt den Rest nicht. Drei Repositories deklarieren
`restrictions: null` und haben trotzdem gar keinen Schutz. Eines hat Schutz mit
null Kontexten, obwohl es einen deklariert. Ein weiteres erhält drei seiner vier
deklarierten Kontexte.

## Entscheidung

Einen Check bauen, der deklarierte gegen tatsächliche Protection über das
Portfolio vergleicht, und ihn nach Zeitplan laufen lassen. Erst danach anhand
seiner Ergebnisse entscheiden, was sich in den Commons ändert.

## Erwogene Alternativen

**`restrictions` jetzt aus den `develop`-Commons entfernen.** Vorerst verworfen.
Es würde den Fall dieses Repositories schließen und vier ungeklärte unberührt
lassen, während es aussähe, als wäre das Problem gelöst.

**Jeden Consumer `restrictions: null` deklarieren lassen.** Verworfen. Es
wiederholt Boilerplate in jedem Repository, und ein Vergessen scheitert lautlos,
was genau der Mechanismus hinter diesem Problem ist.

**Das Portfolio in eine Organisation überführen.** Zurückgestellt. Damit
funktionierte `restrictions.apps` wie vorgesehen, aber die Folgen reichen weit
über Branch Protection hinaus.

## Folgen

Die prägende Eigenschaft dieser Fehlerklasse ist Unsichtbarkeit. Es gibt keinen
Fehler, kein Log und keinen roten Check. Das Repository sieht konfiguriert aus
und ist es nicht. Niemand merkt es, bis ein Merge durchgeht, der hätte blockiert
werden müssen. Ein Vergleichs-Check adressiert diese Eigenschaft statt eines
einzelnen Vorkommens.

Solange der Check fehlt, ist jede Behauptung, ein Required Check sei in diesem
Portfolio aktiv, unbelegt. [ADR-003](adr-003-workflow-validation-gate.md) fügt
einen Required Check hinzu und erbt diesen Zweifel. Seine Akzeptanzkriterien
verlangen deshalb eine Prüfung über die API statt über die Einstellungsseite.

Die offene Frage, ob `restrictions` auf `develop` überhaupt etwas bringt, bleibt
offen. Die Commons begründen es für `master`, wo die Release-Kaskade mit einem
App-Token pusht. Diese Begründung überträgt sich nicht ohne Weiteres.
