# Statische Tests

Führt ein minimales Bündel statischer Analyse bei jedem Pull-Request und bei jedem Push auf den Default-Branch aus und liefert schnelles Feedback ohne externe Dienste.

- [`pre-commit`](https://pre-commit.com), in einer festgelegten Version installiert, führt die in `.pre-commit-config.yaml` definierten Hooks auf allen Dateien aus; [`actions/cache`](https://github.com/actions/cache), auf einen vollständigen Commit-SHA gepinnt, cacht die Hook-Umgebungen (siehe [Cache der Hook-Umgebungen](#cache-der-hook-umgebungen))

---

## Verwendung

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  pull_request:
  push:
    branches: [develop] # durch den eigenen Default-Branch ersetzen

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
```

!!! tip "Erforderlicher Status-Check"
    Kombiniere den Workflow mit einer Branch-Protection-Regel, die den Check `static / Static CI Tests` verlangt — siehe [Settings](../probot/settings.md).

!!! warning "Fork-Pull-Requests brauchen den Trigger `pull_request`"
    Ein Fork pusht nie in das Basis-Repository. Mit einem reinen Push-Trigger meldet sich der erforderliche Check bei einem Pull-Request aus einem Fork nie, und dieser Pull-Request bleibt blockiert. `pull_request_target` ist keine Alternative. Standardmäßig checkt es den Basis-Branch aus, der erforderliche Check wird also grün, ohne die Änderungen des Pull-Requests zu testen. Checkt man stattdessen den Head des Pull-Requests aus, läuft der Code des Forks mit dem Schreib-Token und den Secrets des Basis-Repositorys. Bei einem Fork-Pull-Request überspringt `reusable-trivy.yaml` den Upload seines Scan-Berichts in den Security-Tab, weil das Token dort nur Leserechte hat.

---

## Fork-Wächter

Erforderliche Checks wie `static / Static CI Tests` laufen bei `pull_request`, und GitHub führt einen `pull_request`-Workflow aus dem Merge-Commit des Pull-Requests aus. Bei einem Fork-Pull-Request stammen die Workflow-Dateien und die Skripte, die sie aufrufen, aus dem Fork. Ein Fork kann sie also so lange ändern, bis jeder Job durchläuft. Ein erforderlicher Kontext nennt nur die App und den Check, daher erfüllt ihn auch ein Check, den der Fork definiert.

`reusable-fork-guard.yaml` ist der Check, den ein Fork nicht umschreiben kann. Rufe ihn aus einem `pull_request_target`-Workflow auf und verlange seinen Kontext neben den anderen:

```yaml title=".github/workflows/fork-guard.yaml"
on:
  pull_request_target:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read

jobs:
  fork-guard:
    permissions:
      contents: read
      statuses: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-fork-guard.yaml@<tag>
```

Der Workflow meldet sein Ergebnis als Commit-Status `fork-guard`, und diesen Status verlangst du als Kontext. Der Check schlägt fehl, wenn der Pull-Request aus einem Fork stammt und einen geschützten Pfad hinzufügt, ändert, entfernt oder umbenennt. Standardmäßig sind das `.github/*`, `scripts/*`, `actions/*`, das Taskfile und `taskfiles/*`, `.pre-commit-config.yaml`, jede `requirements*.txt`, die Konfigurationsdateien von pytest und coverage sowie `mkdocs.yml`. Mit `protected-paths` ersetzt du die Liste. Jede Zeile ist ein Bash-Muster, und `*` passt auch auf `/`. Ein Pull-Request aus einem Branch desselben Repositorys besteht den Check. Um eine berechtigte Fork-Änderung an einem geschützten Pfad zu übernehmen, pusht ein Maintainer sie erneut auf einen Branch des Repositorys.

!!! warning "Warum `pull_request_target` hier sicher ist"
    `pull_request_target` führt die Definition aus dem Default-Branch aus, der Pull-Request kann also weder den Check noch seine Liste ändern. Der Workflow checkt nichts aus und liest keinen Dateiinhalt. Er listet die geänderten Dateinamen über die Compare-API und vergleicht sie als reine Zeichenketten. Sein einziges Schreibrecht ist `statuses`, um das Ergebnis zu melden. Füge ihm keinen Checkout hinzu.

!!! warning "Den Status verlangen, nicht den Check-Run"
    Der Check-Run des Jobs heißt `fork-guard / Protected Paths`. Verlange diesen Namen nicht: Ein Fork kann einen Workflow mit einem gleichnamigen Job hinzufügen, der durchläuft, und dieselbe App meldet dann beide Check-Runs. Einen Commit-Status kann ein Fork nicht setzen, weil das Token seines `pull_request`-Laufs nur Leserechte hat.

!!! info "Den Kontext einführen"
    `pull_request_target` führt die Workflow-Datei aus dem Basis-Branch aus. Merge den Workflow vor oder zusammen mit der Änderung, die seinen Kontext verlangt. Die Branch-Protection ändert sich erst, wenn die Settings den Default-Branch erreichen, und dann liegt der Workflow schon dort.

---

## Cache der Hook-Umgebungen

Der Workflow cacht `~/.cache/pre-commit`, wo pre-commit die Hook-Umgebungen installiert. Der Cache-Key setzt sich aus dem Betriebssystem-Release des Runners, der installierten pre-commit-Version, dem Python-Installationspfad und einem Hash der `.pre-commit-config.yaml` zusammen. Ein neues Ubuntu-Image hinter `ubuntu-latest` oder eine neue pre-commit-Version startet deshalb einen frischen Cache, statt Umgebungen wiederherzustellen, die für ein anderes System gebaut wurden.

Wiederherstellen und Speichern sind getrennte Schritte. Der Workflow speichert den Cache nur in einem `pull_request`-Lauf, nur bei einem Cache-Miss und bevor `pre-commit run` irgendeinen Hook ausführt. Einen Cache, den ein Pull-Request-Lauf speichert, sieht nur dieser Pull-Request. Läufe auf dem Default-Branch, Pushes auf andere Branches und `pull_request_target`-Läufe stellen höchstens wieder her und speichern nie. So kann Hook-Code keine Hook-Umgebungen in den Cache des Default-Branches schreiben, aus dem jeder Branch des Repositorys wiederherstellt.

!!! info "Weniger Cache-Treffer"
    Der Default-Branch erhält nie einen gespeicherten Cache. Läufe auf dem Default-Branch und der erste Lauf jedes Pull-Requests installieren die Hook-Umgebungen von Grund auf, der nächste Lauf desselben Pull-Requests stellt sie wieder her. Ein Aufrufer, der den Workflow nur bei `push` auslöst, nutzt den Cache nie.

!!! warning "Restrisiko"
    Hook-Code läuft auf dem Runner und kann das Token lesen, mit dem der Runner den Cache-Dienst anspricht. Damit kann Hook-Code weiterhin jeden Cache-Eintrag im Scope des aktuellen Laufs schreiben, auf dem Default-Branch also im Scope des Default-Branches. Die Trennung von Wiederherstellen und Speichern schließt diesen Weg nicht. Das gelingt nur, wenn die Hooks isoliert vom Runner laufen, zum Beispiel in einem Container ohne den Runner-Kontext.

---

## Docker-Hub-Rate-Limits

Ein Hook mit `language: docker_image` zieht sein Image bei jedem Lauf, und pre-commit kann es nicht cachen: Diese Sprache setzt `ENVIRONMENT_DIR = None` mit `install_environment = no_install`, das Image bleibt also im Store des Docker-Daemons und landet nie unter `~/.cache/pre-commit` — dem einzigen Pfad, den dieser Workflow an `actions/cache` übergibt.

Ein anonymer Pull zählt gegen ein Budget, das an der Quell-IP hängt, und GitHub-gehostete Runner teilen sich ihre Ausgangsadressen plattformweit. Die Lane verbraucht damit ein Budget, das jedes andere Repository im selben Runner-Netz ebenfalls verbraucht — eine Rate-Limit-Ablehnung kann einen erforderlichen Check also aus einem Grund rot färben, der nichts mit dem Diff zu tun hat.

Zwei optionale Parameter verschieben die Zählung auf ein Konto-Budget:

| Parameter | Art | Default | Zweck |
| --- | --- | --- | --- |
| `dockerhub-username` | Input | `""` | Docker-Hub-Kontoname. Ein Benutzername ist nicht geheim, deshalb reist er als Input. Leer überspringt den Login-Schritt. |
| `dockerhub-token` | Secret | nicht gesetzt | Docker-Hub-Personal-Access-Token zu diesem Konto. Es muss den Scope „Public Repo Read-only“ haben, weil pre-commit-Hooks im selben Job es lesen können. |

Das Token gehört zu einer eigenen Docker ID, die nur die CI nutzt (ein Bot-Konto), nicht zu einer persönlichen, und bekommt ein Ablaufdatum und regelmäßige Rotation. Da Hook-Code es lesen kann, verbraucht ein Leck dann nur das Pull-Kontingent dieses Kontos und legt keine anderswo genutzte Identität offen. Aus demselben Grund persistiert der Workflow das Checkout-Token nicht (`persist-credentials: false`). Ein Hook, der von `origin` fetcht, funktioniert deshalb nur in einem öffentlichen Repository, und ein privater Aufrufer braucht einen eigenen Workflow.

```yaml title=".github/workflows/build-static-tests.yaml"
jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
    with:
      dockerhub-username: ${{ vars.DOCKERHUB_USERNAME }}
    secrets:
      dockerhub-token: ${{ secrets.DOCKERHUB_TOKEN }}
```

!!! info "Beide Parameter sind optional"
    Ein Aufrufer, der keinen von beiden übergibt, läuft exakt so wie vor ihrer Einführung: Der Login-Schritt wird übersprungen, die Pulls bleiben anonym. Ein Repository, dessen `.pre-commit-config.yaml` keinen `language: docker_image`-Hook deklariert, gewinnt nichts durch das Setzen.

!!! warning "Ein defektes Credential degradiert, es lässt den Lauf nicht scheitern"
    Der Login-Schritt trägt `continue-on-error`. Ein abgelaufenes Token, ein Token, das einem Fork-Pull-Request vorenthalten wird, oder ein Benutzername ohne Token fallen alle auf anonyme Pulls zurück und erzeugen eine Warning-Annotation. Hart zu scheitern würde die erforderliche Lane bei jedem Pull-Request rot färben — schlimmer als das Rate-Limit, das der Login vermeidet. Das Run-Log nennt immer den verwendeten Modus.

!!! question "Warum kein GHCR-Mirror?"
    Die Hooks auf einen Mirror zu zeigen, braucht ein `entry:`-Override und entkoppelt damit den Image-Tag vom `rev:` des Hooks. Genau dieses `rev:` beobachtet die Update-Automatisierung — der Mirror würde unbeobachtet altern.

---

## Shell-Lint

`reusable-shellcheck.yaml` prüft Shell-Skripte mit [ShellCheck](https://www.shellcheck.net/). Der Workflow installiert ein festgelegtes ShellCheck-Release und prüft dessen Prüfsumme, bevor er es ausführt; die Version ändert sich also nur mit einem Release dieses Repositorys. Er prüft jede passende Datei, nicht nur die in einem Pull-Request geänderten, und meldet jeden Befund als Annotation: als Fehler, als Warnung oder, für die Stufen `info` und `style`, als Hinweis. Er braucht nur `contents: read` und schreibt nichts in den Pull-Request.

```yaml title=".github/workflows/build-static-tests.yaml"
jobs:
  shellcheck:
    permissions:
      contents: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-shellcheck.yaml@<tag>
```

| Input | Standard | Zweck |
| --- | --- | --- |
| `fail_level` | `error` | Schweregrad, ab dem der Job fehlschlägt: `error`, `warning`, `info`, `any` oder `none`. Befunde darunter annotiert der Job, ohne fehlzuschlagen. |
| `path` | `.` | Basisverzeichnis der Suche, eines pro Zeile. Ein Pfad, den es nicht gibt, lässt den Job fehlschlagen. |
| `pattern` | `*.sh` | Dateinamensmuster der Skripte, eines pro Zeile. |
| `exclude` | `*/.git/*` | Pfadmuster, das ausgelassen wird, eines pro Zeile. Ein Wert ersetzt den Standard. |
| `check_all_files_with_shebangs` | `false` | Prüft zusätzlich jede Datei, deren erste Zeile `sh`, `bash`, `dash` oder `ksh` als Interpreter nennt, unabhängig vom Dateinamen. |
| `shellcheck_flags` | `--external-sources` | Flags für ShellCheck, an Leerzeichen und Zeilenenden getrennt. Das Ausgabeformat setzt der Workflow selbst. |

Der Job ist grün, wenn keine Datei passt. Ein Repository ohne Shell-Skripte kann den Workflow daher schon aufrufen, bevor es welche hat.

Der Workflow liefert kein Artefakt, derselbe Aufruf funktioniert also als Gate in einem Release-Pfad. Mit `needs:` vor den veröffentlichenden Job gesetzt, stoppt ein Befund ab `fail_level` die Veröffentlichung:

```yaml title=".github/workflows/release-publish.yml"
jobs:
  shellcheck:
    permissions:
      contents: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-shellcheck.yaml@<tag>
  publish:
    needs: shellcheck
    permissions:
      contents: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@<tag>
```

!!! info "Skripte in Workflow-Dateien"
    Der Workflow liest nur Skriptdateien. Die Shell in den `run:`-Blöcken von Workflow-Dateien deckt `reusable-actionlint.yaml` ab.

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../../.github/workflows/reusable-pre-commit.yaml"
%}
```
