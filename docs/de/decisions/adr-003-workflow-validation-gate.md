# ADR-003: Workflow-Gültigkeit über einen Required Check absichern

**Status:** Angenommen (2026-08-01) · **Issue:** [#398](https://github.com/nolte/gh-plumbing/issues/398)

## Kontext

`reusable-hacs-validate.yaml` scheiterte fünf Wochen lang an GitHubs
Workflow-Validierung. Die Datei nutzte eine Expression im `uses:` eines Steps,
was GitHub Actions nicht unterstützt. Sie ließ sich also nie parsen, der Workflow
lief nie, und kein Consumer konnte ihn aufrufen.

GitHub meldet das durchaus. Es erzeugt einen Run, benannt nach dem Dateipfad, mit
null Jobs. Dieser Run stand ab dem 2026-06-26 rot auf `develop`. Übersehen wurde
er, weil er nichts blockiert, weil er nach einem Pfad statt nach einem Workflow
heißt, und weil er nur wieder auftaucht, wenn die Datei selbst sich ändert.

Das Signal existierte. Niemand handelte darauf.

## Entscheidung

`reusable-actionlint.yaml` hinzufügen, in `build-static-tests.yaml` einhängen und
den Job-Namen in die Required Status Checks für `develop` aufnehmen.

Separat die defekte Datei reparieren: den Action-Digest direkt eintragen und den
Input entfernen, der die nicht unterstützte Expression speiste. Dieser Input
existierte ausschließlich dafür, es gibt also keine Variante, die beides behält.

## Erwogene Alternativen

**Den Check hinzufügen, ohne ihn verpflichtend zu machen.** Verworfen, anhand der
Evidenz dieses Issues. Ein nicht blockierendes Signal existierte bereits und
wurde fünf Wochen ignoriert. Ein zweites würde denselben Fehler mit besserem
Werkzeug wiederholen.

**Stattdessen die vorhandenen Validierungs-Runs beobachten.** Verworfen. Das
verlässt sich darauf, dass jemand hinschaut, und genau das hat hier versagt.
`actionlint` findet zudem mehr: ungültige Expression-Kontexte, falsche
`uses:`-Formen, Shell-Probleme in `run:`-Blöcken und Typfehler in Inputs.

**Den defekten Input als deprecated No-Op behalten.** Verworfen. Ein
Deprecation-Shim schützt funktionierende Aufrufer, und es gab keine.

## Folgen

Der Check kommt als wiederverwendbarer Workflow statt als Inline-Schritte, damit
Consumer ihn erben. Eine Bibliothek geteilter Workflows, die nur die eigenen
Workflows lintet, würde denselben Fehler eine Ebene höher wiederholen.

Der erste Lauf wird mehr als eine defekte Datei finden. Dreißig Workflow-Dateien
wurden nie gelintet. Deshalb landet zuerst das Reusable, dann wird der Baum
sauber, und erst zuletzt kommt der Required Context dazu. Umgekehrt würde jeder
Pull Request an unbeteiligten Altbefunden hängen.

Consumer erhalten einen Check, der einen Pull Request rot macht, dessen
Workflow-Dateien sich nicht parsen lassen. Repositories mit bereits ungültigen
Workflow-Dateien bekommen diese zu sehen.
