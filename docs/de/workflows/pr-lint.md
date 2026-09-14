# Pull-Request-Lint

Prüft Titel und Body eines Pull Requests gegen die Pull-Request-Workflow-Spec des Portfolios (`spec/project/pull-request-workflow/` in `nolte/claude-shared`):

- den Conventional-Commits-Titel mit einem Typ aus `feat`, `fix`, `chore`, `docs`, `exp`
- die fünf Pflichtabschnitte im Body in fester Reihenfolge sowie nicht leere Abschnitte Summary, Changes und Testing
- einen Abschnitt `## Class sweep` bei jedem `fix`-Pull-Request
- `Originating source:` und `Dispatched specialist:` in `## Risk / rollout notes`, wenn `## Linked issues` ein Issue mit dem Audit-Label referenziert
- optional eine Zeile `Refs spec/<topic>/<slug>/`, wenn die Änderung Pfade außerhalb von `spec/` berührt

Ein Pull Request eines freigegebenen Dependency-Bots durchläuft nur die Titelprüfung.

---

## Verwendung

```yaml title=".github/workflows/pr-lint.yml"
on:
  pull_request:
    types: [opened, edited, synchronize, ready_for_review]

permissions:
  contents: read

jobs:
  pr-lint:
    permissions:
      contents: read
      pull-requests: read
      issues: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-pr-lint.yaml@<tag-or-commit-sha>
    with:
      spec-anchor: false
```

Der Aufrufer muss `pull-requests: read` und `issues: read` gewähren, denn ein aufgerufener Workflow kann die Rechte seines Aufrufers nicht erweitern.

| Input | Default | Wirkung |
|---|---|---|
| `python-version` | `3.14` | Python-Version für den Checker |
| `audit-label` | `audit` | Label, das ein Audit-Tracking-Issue markiert; leer schaltet die Traceability-Regel ab |
| `spec-anchor` | `false` | Verlangt eine Zeile `Refs spec/…`, wenn sich Pfade außerhalb von `spec/` ändern |

!!! tip "Erforderlicher Status-Check"
    Verlange den Context `pr-lint / PR Lint` auf `develop`; der Name setzt sich aus der Job-ID des Aufrufers und dem Job-Namen dieses Workflows zusammen — siehe [Settings](../probot/settings.md).

!!! note "Der Checker läuft am gepinnten Commit"
    Der Workflow checkt seinen eigenen Checker an dem Commit aus, den der Aufrufer gepinnt hat, über `job.workflow_repository` und `job.workflow_sha`. Das Repository des Aufrufers checkt er nie aus, sodass ein Pull Request die Regeln, nach denen er geprüft wird, nicht ändern kann.

---

## Zentrale Konfiguration

```yaml title=".github/workflows/reusable-pr-lint.yaml"
{%
   include "../../../.github/workflows/reusable-pr-lint.yaml"
%}
```
