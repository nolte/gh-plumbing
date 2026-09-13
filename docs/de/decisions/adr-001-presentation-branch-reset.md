# ADR-001: Die Schreibstrategie für den Präsentationsbranch aus dem Ziel ableiten

**Status:** Überarbeitet (2026-09-14) · **Issues:** [#384](https://github.com/nolte/gh-plumbing/issues/384), [#414](https://github.com/nolte/gh-plumbing/issues/414)

!!! warning "Was diese Überarbeitung ändert"
    Die ursprüngliche Entscheidung — immer mit `force-with-lease` zurücksetzen —
    ging davon aus, dass eine Strategie für jeden Präsentationsbranch genügt.
    Das trifft nicht zu. Das Zurücksetzen löst ein Linear-History-Ruleset und
    scheitert selbst an einem Branch, der Force-Pushes verbietet — genau die
    Konfiguration, die der `master` dieses Repositories trägt. Zwei Releases
    liefen grün durch, während `master` auf `v1.1.26` stehen blieb. Die
    Entscheidung unten wählt jetzt je Ziel; der ursprüngliche Text bleibt unter
    „Abgelöste Entscheidung" erhalten, weil seine Begründung weiterhin erklärt,
    warum auch der Merge allein nicht ausreicht.

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

Zwei reale Consumer-Konfigurationen verbieten Gegensätzliches:

| Regel am Ziel | Verbietet | Bricht |
|---|---|---|
| Linear History | Merge-Commits | den `/merges`-API-Aufruf |
| keine Force-Pushes | History-Rewrites | den `force-with-lease`-Push |
| `pull_request`-Ruleset-Regel | jeden direkten Schreibzugriff | beides |

Eine Erhebung der vier Präsentationsbranches im Portfolio fand drei mit einer
`pull_request`-Regel, davon zwei **ganz ohne Bypass-Actor** — dorthin schreibt
kein Credential, das dieser Workflow halten kann.

## Entscheidung

Die Protection des Ziels lesen und die Strategie daraus wählen:

- **Merge-Commits erlaubt** → die `/merges`-API. Bevorzugt, wenn beides ginge,
  weil sie den Branch ergänzt statt ihn umzuschreiben.
- **Merge verboten, Force-Push erlaubt** → `force-with-lease`-Push des
  Release-Tags, die Strategie dieser ADR in ihrer ursprünglichen Fassung.
- **weder noch** → verweigern, mit einer Diagnose, die die blockierende Regel
  benennt, und den Lauf scheitern lassen.

Beide Mechanismen werden konsultiert, denn klassische Branch-Protection und
Rulesets sind unabhängig voneinander und jeder kann jede Operation verbieten.
Ein nicht lesbarer Endpunkt gilt als restriktiv, nicht als erlaubend: aus einem
fehlgeschlagenen Lesen auf „ungeschützt" zu schließen ist genau der Fehler, den
[#421](https://github.com/nolte/gh-plumbing/issues/421) im Branch-Protection-Audit
gefunden hat.

## Erwogene Alternativen

**Die Release-App vom Ruleset ausnehmen.** In der ursprünglichen Entscheidung
verworfen und als *alleinige* Antwort weiterhin verworfen — es höhlt eine Regel
aus, die der Consumer bewusst gesetzt hat, und muss in jedem Repository
wiederholt werden. Für ein einzelnes Ziel bleibt es die richtige
Operator-Maßnahme, und die Fehlermeldung sagt das auch.

**Dokumentieren, dass Consumer kein Linear-History-Ruleset setzen dürfen.**
Verworfen. Es verlagert eine Einschränkung auf den Consumer, statt das geteilte
Werkzeug zu reparieren.

**Die Kaskade abschaffen und Consumer auf den Release-Tag verweisen.** In
[#414](https://github.com/nolte/gh-plumbing/issues/414) erwogen und hier nicht
gewählt. Es beseitigt die Fehlerklasse vollständig, statt sie zu umgehen, ändert
aber portfolio-weit die Bedeutung von `master` — eine größere Entscheidung als
die, die diese ADR trifft.

**Nur Fast-Forward.** Verworfen. Das funktioniert nur, wenn der
Präsentationsbranch nie divergiert, und der `master` dieses Repositories trägt
bereits synthetische Merge-Commits, die es auf `develop` nie gab.

## Folgen

Der Fehlschlag ist jetzt laut. Ein Ziel, das der Workflow nicht beschreiben
kann, lässt den Lauf scheitern und benennt die blockierende Regel, statt einen
veralteten Präsentationsbranch hinter einem grünen Release zurückzulassen — der
Zustand, den `v2.0.0` und `v2.0.1` beide erreichten und der sechs Wochen
unbemerkt blieb.

Consumer, deren Präsentationsbranch Merge-Commits erlaubt, sehen bei jedem
Release keinen History-Rewrite mehr, sondern wieder einen Merge-Commit wie vor
#404. Nur die Branches, die Merges verbieten, behalten das Zurücksetzen.

Der Verzicht auf `devmasx/merge-branch` übersteht die Überarbeitung: Der
Merge-Pfad ruft die `/merges`-API direkt auf, die Third-Party-Action bleibt also
aus einem Schritt heraus, der `contents: write` gegen einen geschützten Branch
hält.

Wer lokale Commits auf einem Präsentationsbranch hält, muss sie weiterhin vor
einem Release verschieben. Dieser Branch ist als automatisch aktualisiert
dokumentiert und nicht als Ort zum Committen, und der Reset-Pfad schreibt ihn
nach wie vor um.

## Abgelöste Entscheidung (2026-08-01)

Erhalten, weil ihre Begründung weiterhin erklärt, warum auch ein Merge allein
nicht genügt — ein Linear-History-Ruleset weist den `/merges`-Aufruf rundweg ab:

> Den Merge durch einen `force-with-lease`-Push des Release-Tags auf den
> Zielbranch ersetzen. Der Lease-Wert stammt aus dem Lesen der Ziel-Ref
> unmittelbar vor dem Push, sodass eine nebenläufige Aktualisierung abbricht
> statt Daten zu verlieren.

Ihre benannten Folgen galten, wie sich zeigte, nur für ein Ziel, das
Force-Pushes erlaubt: dass der Präsentationsbranch zum exakten Spiegel des
Release-Tags wird und das Zurücksetzen die synthetischen Merge-Commits des alten
Mechanismus verwirft. Auf einem Ziel, das Force-Pushes verbietet, geschah nichts
davon — der Push wurde abgewiesen und der Branch blieb, wo er war.
