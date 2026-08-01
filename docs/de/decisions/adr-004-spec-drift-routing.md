# ADR-004: Den Q2-Spec-Drift-Cluster über die Roadmap führen

**Status:** Angenommen (2026-08-01) · **Issue:** [#386](https://github.com/nolte/gh-plumbing/issues/386)

## Kontext

Das Spec-Drift-Audit 2026-Q2 von `nolte/claude-shared` hinterließ ein Bündel von
Befunden, die in dieses Repository gehören und nicht in einen Consumer. Eine
Referenz auf einen wiederverwendbaren Workflow zu bauen, den es nicht gibt, würde
die CI eines Consumers brechen. Die Arbeit muss also zuerst hier geschehen.

Das Bündel spannt vier getrennte Outcomes:

1. ein PR-Lint-Reusable, dazu die Übernahme durch Consumer und ein neuer Required Check
2. fünf Härtungen an `reusable-release-publish.yml`, mehrere davon Gates
3. zwei Pre-Release-Gates, für Doku-Frische und Release-Notes-Prosa
4. ein `exp/`-`autolabeler`-Eintrag in den Release-Drafter-Commons

## Entscheidung

Ein Roadmap-Item für die Outcomes eins bis drei anlegen und in Features zerlegen.
Den `exp/`-`autolabeler`-Eintrag separat und vorab ausliefern.

## Erwogene Alternativen

**In vier Issues aufteilen und einzeln abarbeiten.** Verworfen. Die
Issue-Orchestration-Spec führt Arbeit, die mehr als ein Outcome umfasst, in die
Planungsebene. Vier einzeln abgearbeitete Issues würden sie umgehen.

**Zuerst die Release-Härtungen umsetzen und den Rest später planen.** Verworfen.
Das mischt Routen, und die Spec verbietet eine Teilumsetzung, die den Rest
ungeplant lässt.

## Folgen

Alle drei Roadmap-Items dieses Repositories tragen `status: done`. Es braucht
also ein neues statt einer Änderung an einem bestehenden.

Der `exp/`-`autolabeler`-Eintrag ist eine einzelne Ergänzung an einer
Commons-Datei. Er hängt an nichts anderem im Bündel, und nichts hängt an ihm. In
einem Sammel-Item würde er auf einen Sprint warten, den er nicht braucht. Ihn
vorzuziehen ist eine hier festgehaltene Scope-Entscheidung, kein ungeplanter
Rest.

Zwei Abhängigkeiten zählen bei der Planung. Die Release-Härtung betrifft ein
anstehendes Major-Release, und zwei ihrer Punkte sichern gegen Fehler ab, die
bereits einmal aufgetreten sind. Der PR-Lint-Check fügt einen Required Status
Context hinzu, von dem sich laut [ADR-002](adr-002-branch-protection-verification.md)
noch nicht belegen lässt, dass er greift.
