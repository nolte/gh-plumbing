# ADR-001: Präsentationsbranch auf den Release-Tag zurücksetzen

**Status:** Angenommen (2026-08-01) · **Issue:** [#384](https://github.com/nolte/gh-plumbing/issues/384)

## Kontext

Nach einem Release aktualisiert `reusable-release-cd-refresh-master.yml` den
Präsentationsbranch (`main` oder `master`), damit er dem neuesten Release folgt.
Bisher geschah das mit `devmasx/merge-branch`, das die GitHub-`merges`-API
aufruft. Diese API erzeugt einen Merge-Commit.

Ein Consumer, dessen Präsentationsbranch ein Linear-History-Ruleset trägt, weist
den Aufruf ab:

```text
POST /repos/nolte/workstation/merges: 409
This branch must not contain merge commits.
```

Das Release selbst wird veröffentlicht und die Doku ausgeliefert. Nur der
Präsentationsbranch bleibt stehen, weshalb der Fehler leicht übersehen wird.

Der Branch driftet zudem. In diesem Repository trägt `master` synthetische
Merge-Commits, die es auf `develop` nie gab, und `master` ist kein Ancestor von
`develop`. Ein einfacher Fast-Forward-Push wird deshalb ebenfalls abgewiesen.

## Entscheidung

Den Merge durch einen `force-with-lease`-Push des Release-Tags auf den
Zielbranch ersetzen. Der Lease-Wert stammt aus dem Lesen der Ziel-Ref unmittelbar
vor dem Push, sodass eine nebenläufige Aktualisierung abbricht statt Daten zu
verlieren.

## Erwogene Alternativen

**Die Release-App vom Ruleset ausnehmen.** Verworfen. Es höhlt eine Regel aus,
die der Consumer bewusst gesetzt hat, und muss in jedem Repository wiederholt
werden.

**Dokumentieren, dass Consumer kein Linear-History-Ruleset setzen dürfen.**
Verworfen. Es verlagert eine Einschränkung auf den Consumer, statt das geteilte
Werkzeug zu reparieren.

## Folgen

Der Präsentationsbranch wird zum exakten Spiegel des Release-Tags, was er immer
zu sein behauptet hat. Das Zurücksetzen verwirft die synthetischen Merge-Commits
des alten Mechanismus. Nichts referenziert sie.

Der Workflow hängt nicht länger von `devmasx/merge-branch` ab, was eine
Third-Party-Action aus einem Schritt entfernt, der `contents: write` gegen einen
geschützten Branch hält.

Consumer sehen beim nächsten Release einen History-Rewrite auf dem
Präsentationsbranch. Dieser Branch ist als automatisch aktualisiert dokumentiert
und nicht als Ort zum Committen, es sollte also keine Arbeit verloren gehen. Wer
dort lokale Commits hält, muss sie vorher verschieben.
