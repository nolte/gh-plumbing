# Statische Tests

Führt ein minimales Bündel statischer Analyse bei jedem Pull-Request und bei jedem Push auf den Default-Branch aus und liefert schnelles Feedback ohne externe Dienste.

- [`pre-commit/action`](https://github.com/pre-commit/action) führt die in `.pre-commit-config.yaml` definierten Hooks aus
- [`zbeekman/EditorConfig-Action`](https://github.com/zbeekman/EditorConfig-Action) prüft `.editorconfig`-Regeln

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

## Docker-Hub-Rate-Limits

Ein Hook mit `language: docker_image` zieht sein Image bei jedem Lauf, und pre-commit kann es nicht cachen: Diese Sprache setzt `ENVIRONMENT_DIR = None` mit `install_environment = no_install`, das Image bleibt also im Store des Docker-Daemons und landet nie unter `~/.cache/pre-commit` — dem einzigen Pfad, den `pre-commit/action` an `actions/cache` übergibt.

Ein anonymer Pull zählt gegen ein Budget, das an der Quell-IP hängt, und GitHub-gehostete Runner teilen sich ihre Ausgangsadressen plattformweit. Die Lane verbraucht damit ein Budget, das jedes andere Repository im selben Runner-Netz ebenfalls verbraucht — eine Rate-Limit-Ablehnung kann einen erforderlichen Check also aus einem Grund rot färben, der nichts mit dem Diff zu tun hat.

Zwei optionale Parameter verschieben die Zählung auf ein Konto-Budget:

| Parameter | Art | Default | Zweck |
| --- | --- | --- | --- |
| `dockerhub-username` | Input | `""` | Docker-Hub-Kontoname. Ein Benutzername ist nicht geheim, deshalb reist er als Input. Leer überspringt den Login-Schritt. |
| `dockerhub-token` | Secret | nicht gesetzt | Docker-Hub-Access-Token zu diesem Konto. Ein Lese-Token genügt; hier wird nichts gepusht. |

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

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../../.github/workflows/reusable-pre-commit.yaml"
%}
```
