---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "469"
classification: "security"
secondary-classes: ["infra"]
route: "direct"
status: approved
created: "2026-11-17"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #469 — Pre-commit hook code can read the persisted checkout token and Docker Hub credentials
- **URL**: https://github.com/nolte/gh-plumbing/issues/469
- **Labels**: cicd, security
- **Linked items**: #466 / PR #470 (Herkunft: SEC-003 aus dem `code-security-reviewer`-Lauf); keine schließenden PRs
- **Prior art checked**: keine offenen PRs; 5 Checkouts im Repo setzen bereits `persist-credentials: false` (`reusable-docs-freshness`, `reusable-pr-lint`, `reusable-release-archive`, `reusable-release-publish` job=publish) → Muster vorhanden
- **Autor / Trust**: `nolte` (Repo-Owner) → vertrauenswürdig
- **Requirements-Gate**: kein Requirement-Artefakt; **Operator-Override 2026-11-17** — Akzeptanzkriterien des Issues gelten

## Classification

- **Primary class**: security
- **Secondary class(es)**: infra
- **Rationale**: Credentials bleiben für Drittcode (pre-commit-Hooks) auf dem Runner lesbar; Least-Privilege-Härtung eines öffentlichen Reusables.
- **Asserted cause verified**: confirmed —
  - `gh api 'repos/actions/checkout/contents/action.yml?ref=d23441a…'` → `persist-credentials: default: true`; README am selben SHA: „stores credentials in a separate file under `$RUNNER_TEMP`" (Datei vom Job-User lesbar).
  - `gh api 'repos/docker/login-action/contents/action.yml?ref=c94ce9f…'` → `logout: default 'true'`, ausgeführt im `post:`-Step, also nach `Run pre-commit`.
  - `reusable-pre-commit.yaml:88-89` Checkout ohne `with:`; `:117` Login vor `:178` pre-commit.

## Messungen (Research)

- Alle 10 Consumer des Reusables sind `public` (`gh api repos/nolte/<r> -q .visibility`): claude-goose, cookiecutter-gh-project, esphome-configs, k8s-home-lab, kamerplanter, pre-commit-hooks, taskfiles, vale-style, workstation, gh-plumbing. → anonymer `git fetch` gegen origin funktioniert; `persist-credentials: false` bricht keinen Hook. Workflow-Permission ist `contents: read` → kein Push möglich, also auch keiner, der wegfiele.
- Docker-Hub-Credentials übergibt nur `nolte/kamerplanter` (`gh search code dockerhub-username --owner nolte`), Aufruf gepinnt auf `9048eaf… # v2.2.1`.
- `docker_image`-Hooks laufen im Container und sehen `~/.docker/config.json` nicht; Host-Hooks (`language: python/system/script`) können sie lesen. `docker run` braucht die Credentials während des Hook-Laufs → technisch nicht vor den Hooks entfernbar (Vorab-Pull im Workflow-Header Z. 35–44 begründet verworfen).

## Scope

- **In scope**:
  - `reusable-pre-commit.yaml`: `persist-credentials: false` am Checkout mit Begründungskommentar.
  - `dockerhub-token`-Secret-Beschreibung: „Public Repo Read-only"-PAT **verpflichtend** statt „sufficient", mit Begründung (Host-Hooks können `~/.docker/config.json` lesen).
  - Docs `docs/{en,de}/workflows/static-tests.md` Z. 41 entsprechend.
- **Out of scope**:
  - Übrige 20 Checkouts ohne explizites `persist-credentials` + Guard → eigenes Issue (P3), Operator-Entscheidung 2026-11-17.
  - Technische Trennung Docker-/Host-Hooks (Operator: Schaden begrenzen genügt).

## Route

- **Decision**: direct — ein Ergebnis, ein PR, kein Roadmap-Eintrag.

## Work packages

### P1 — Credentials im Reusable reduzieren

- **Problem statement**: Hook-Code kann das persistierte Checkout-Token lesen; die Secret-Beschreibung erlaubt einen PAT mit mehr als Read-Rechten.
- **Acceptance criteria**:
  - Checkout-Step in `reusable-pre-commit.yaml` hat `with: persist-credentials: false` + Kommentar (Warum, warum gefahrlos für Consumer).
  - `dockerhub-token`-Beschreibung verlangt einen Public-Repo-Read-only-PAT und nennt das Restrisiko (Host-Hooks lesen `~/.docker/config.json`; Logout erst im post-Step).
  - Header-Kommentar bleibt konsistent; Inputs/Secrets-Namen, Permissions, Job-Name `Static CI Tests` unverändert.
  - actionlint exit 0; im CI-Log von `static / Static CI Tests` fehlt die Checkout-Ausgabe zum Persistieren der Auth (vorher vorhanden) — Vorher/Nachher-Vergleich per `gh run view --log`.
- **Touched files**: `.github/workflows/reusable-pre-commit.yaml`
- **Specialist**: `nolte-engineering:fullstack-developer` (Agent mit Worktree-Pfaden; gleiches Muster wie #466)
- **Depends on**: none

### P2 — Docs nachziehen

- **Acceptance criteria**: EN/DE Z. 41 (`dockerhub-token`-Zeile) verlangen den Read-only-PAT inhaltlich gleich; optional ein Satz zum nicht persistierten Checkout-Token. Vale auf geänderten EN-Zeilen: 0 Errors, < 10 Annotationen.
- **Touched files**: `docs/en/workflows/static-tests.md`, `docs/de/workflows/static-tests.md`
- **Specialist**: `nolte-shared:prose-vale-curator`
- **Depends on**: P1

### P3 — Klassen-Issue anlegen

- **Acceptance criteria**: Issue nennt die 20 übrigen Checkouts (Predicate-Ausgabe), den Vorschlag eines Guards (jeder Checkout legt `persist-credentials` explizit fest; `true` nur mit Begründung) und referenziert #469; im PR unter Risk / rollout notes verlinkt.
- **Specialist**: no matching specialised agent — generalist (Orchestrator)
- **Depends on**: none

### P4 — Verifikation vor PR

- **Acceptance criteria**: `cicd-pipeline-reviewer` + `code-security-reviewer` (diff-scoped) ohne Critical/Warning; pre-commit-Gate exit 0; Predicate auf `reusable-pre-commit.yaml` → 0 Treffer; Diff-Capture nicht leer.
- **Specialist**: `nolte-shared:cicd-pipeline-reviewer`, `nolte-engineering:code-security-reviewer`
- **Depends on**: P1, P2

## Dependency ordering

P3 (sofort, damit referenzierbar) ; P1 → P2 → P4 → PR

## Class sweep (Defektklasse)

- **Klasse**: `actions/checkout` ohne explizite `persist-credentials`-Entscheidung in `.github/workflows/`.
- **Predicate**: YAML-Scan aller Steps mit `uses: actions/checkout@…` ohne `with.persist-credentials` → 21 Treffer auf `develop` (21e2a11).
- **Repaired**: 1 (`reusable-pre-commit.yaml`); Rest 20 → P3-Issue (Per-Site-Entscheidung + öffentliche API von ~17 Reusables; Bedingung (b) der Triage nicht erfüllt, Operator-Entscheidung).
- **Guard**: none in diesem PR — im P3-Issue als Akzeptanzkriterium.

## Risks

- **Ein Consumer-Hook braucht authentifiziertes Git** → gemessen: alle Consumer public, Token nur `contents: read` → keiner betroffen. Ein künftiger privater Consumer, dessen Hook `origin` fetcht, müsste das überschreiben (im Kommentar dokumentiert).
- **Consumer-AC „grün in einem Consumer mit docker_image-Hooks"** ist erst nach Release + Renovate-Bump in kamerplanter messbar (gepinnt auf v2.2.1) → im PR als Post-Release-Verifikation vermerkt; #469 bleibt bis dahin offen oder wird mit Verweis geschlossen (Operator-Entscheid bei Close).
- Security-sensitiver Pfad → P4 Reviews vor PR.

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|

## Dispatch log
