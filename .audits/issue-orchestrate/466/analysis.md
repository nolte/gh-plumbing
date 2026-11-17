---
artifact-type: issue-orchestration-analysis
repo: "nolte/gh-plumbing"
issue: "466"
classification: "security"
secondary-classes: ["infra"]
route: "direct"
status: approved
created: "2026-11-17"
---

# Issue Orchestration — Pre-analysis

## Issue metadata

- **Repository**: nolte/gh-plumbing
- **Issue**: #466 — Replace pre-commit/action so sha_pinning_required can be enabled
- **URL**: https://github.com/nolte/gh-plumbing/issues/466
- **Labels**: cicd, security
- **Linked items**: #462, #463, #465 (Kontext); keine schließenden PRs (`closedByPullRequestsReferences: []`)
- **Prior art checked**: keine offenen PRs zu #466; keine `project/features/`- oder Roadmap-Einträge; `project/requirements/` enthält nur `release-archive-provenance.md` (unbeteiligt)
- **Autor / Trust**: `nolte` (Repo-Owner) → vertrauenswürdig
- **Requirements-Gate**: kein Requirement-Artefakt; **Operator-Override 2026-11-17** — die Akzeptanzkriterien des Issues gelten als Requirement

## Classification

- **Primary class**: security
- **Secondary class(es)**: infra
- **Rationale**: Ziel ist die Durchsetzung von SHA-Pinning für alle Actions inkl. verschachtelter (Lieferketten-Härtung, best-practices §A); kein roter CI-Lauf, daher keine Übergabe an `workflow-health-triage`.
- **Asserted cause verified**: confirmed — `gh api 'repos/pre-commit/action/contents/action.yml?ref=2c7b3805fd2a0fd8c1884dcaebf91fc102a13ecd'` liefert `using: composite` mit Schritt `uses: actions/cache@v4` (Tag, kein SHA). Aufruf in `.github/workflows/reusable-pre-commit.yaml:146`.

## Scope

- **In scope**:
  - `pre-commit/action` in `reusable-pre-commit.yaml` durch direkte Schritte ersetzen (pip-Install mit Versions-Pin, `actions/cache` per SHA, `pre-commit run`), öffentliche Schnittstelle unverändert.
  - Docs `docs/{en,de}/workflows/static-tests.md` und Header-Kommentar des Workflows an die neue Mechanik anpassen.
  - Nach dem Merge: `sha_pinning_required` aktivieren und verifizieren (eigene Operator-Freigabe).
- **Out of scope**:
  - Hash-Pinning von pre-commit (Operator-Entscheidung: Versions-Pin; Hash-Pin bräuchte alle ~9 transitiven Deps inline).
  - Renovate-Tracking von Inline-`pip install x==y`-Pins → eigenes Issue (P5), betrifft die ganze Klasse (pytest, tox, pre-commit).
  - #465 (separat orchestriert).

## Route

- **Decision**: direct
- **Rationale**: ein Ergebnis (Setting aktivierbar), ein PR-Strang, kein Roadmap-Eintrag.

## Messungen (Research)

- Rekursiver Scan aller 31 externen `uses:`-Referenzen in `.github/workflows/` an ihren gepinnten SHAs, inkl. verschachtelter Composites (`trivy-action → setup-trivy → actions/cache/{restore,save}`, `attest-build-provenance → attest`): **einziger Nicht-SHA-Ref ist `pre-commit/action → actions/cache@v4`**. Skript: scratchpad `nested.py`; Ausgabe im Sitzungsprotokoll.
- Alle Reusable-Aufrufe im Repo sind lokal (`uses: ./.github/workflows/…`); kein Remote-Ref per Branch.
- `gh api repos/nolte/gh-plumbing/actions/permissions` → `{"enabled":true,"allowed_actions":"all","sha_pinning_required":false}`.
- Der Reusable läuft im Checkout des Consumers → eine Requirements-Datei aus gh-plumbing steht dort nicht zur Verfügung; der Pin muss inline stehen.
- Inline-pip-Pins werden von keinem Renovate-Manager gelesen: `renovate-configs/common.json` `customManagers` decken nur hacs/hassfest/vale ab; `git log -S'pytest==' -S'tox=='` zeigt nur Handcommits (`nolte`).
- Version: `requirements-dev.txt:5` → `pre-commit==4.5.0`; Cache-Pin-Vorbild `reusable-tf-lint.yaml:42` → `actions/cache@0057852bfaa89a56745cba8c7296529d2fc39830 # v4.3.0`.

## Work packages

### P1 — pre-commit/action durch direkte Schritte ersetzen

- **Problem statement**: Die Composite-Action zieht `actions/cache@v4` per Tag und blockiert damit `sha_pinning_required`.
- **Acceptance criteria**:
  - `reusable-pre-commit.yaml` enthält kein `pre-commit/action` mehr; jede `uses:`-Zeile ist auf 40-Hex-SHA gepinnt.
  - Schritte: `python -m pip install pre-commit==4.5.0`; `python -m pip freeze --local`; `actions/cache@0057852… # v4.3.0` mit `path: ~/.cache/pre-commit` und **wörtlich übernommenem** Key `pre-commit-3|${{ env.pythonLocation }}|${{ hashFiles('.pre-commit-config.yaml') }}` (bestehende Consumer-Caches treffen weiter); `pre-commit run --show-diff-on-failure --color=always --all-files`.
  - Inputs, Secrets, Permissions, Job-Id `static` und Job-Name `Static CI Tests` unverändert.
  - Header-Kommentar (Z. 8–44) nennt nicht mehr `pre-commit/action`, Aussage zum Docker-Image-Cache bleibt korrekt.
  - `actionlint` grün; `static / Static CI Tests` im PR grün.
- **Touched files**: `.github/workflows/reusable-pre-commit.yaml`
- **Specialist**: `nolte-engineering:fullstack-developer` (Agent, mit Worktree-Pfaden). `nolte-shared:cicd-pipeline-design` passt thematisch, arbeitet aber interaktiv in der Sitzung gegen das cwd (Primär-Checkout) und ist auf Pipeline-Design/Audit zugeschnitten, nicht auf einen Schritt-Austausch.
- **Depends on**: none

### P2 — Docs en/de nachziehen

- **Problem statement**: `docs/{en,de}/workflows/static-tests.md` Z. 5 und Z. 33 beschreiben `pre-commit/action`.
- **Acceptance criteria**: Beide Sprachen beschreiben die direkte Installation + `actions/cache` inhaltlich gleich; `vale --minAlertLevel=suggestion` auf `docs/en/...` erzeugt auf den geänderten Zeilen keine Errors und < 10 Annotationen; `mkdocs build --strict` grün (CI `docs / MkDocs Build`).
- **Touched files**: `docs/en/workflows/static-tests.md`, `docs/de/workflows/static-tests.md`
- **Specialist**: `nolte-shared:prose-vale-curator`
- **Depends on**: P1

### P3 — Verifikation vor dem PR

- **Acceptance criteria**: `cicd-pipeline-reviewer` (read-only, unabhängiger Kontext) ohne Befund gegen best-practices §A/§B; Diff-Capture `git -C <worktree> diff --stat origin/develop...HEAD` nicht leer; Repo-Gate `task pre-commit:start` grün; Nested-Scan (Messung oben) erneut über den Branch → 0 Treffer.
- **Specialist**: `nolte-shared:cicd-pipeline-reviewer`; `security-review` auf den Diff (aus der Worktree)
- **Depends on**: P1, P2

### P4 — Setting aktivieren und verifizieren (nach Merge, eigene Operator-Freigabe)

- **Acceptance criteria**: `PUT /repos/nolte/gh-plumbing/actions/permissions` mit `sha_pinning_required: true`; danach `workflow_dispatch` von `build-static-tests.yaml` auf `develop` grün **und** ein PR-Lauf grün; zweiter Lauf zeigt `Cache restored from key: pre-commit-3|…`; bei Pinning-Fehler sofortiger Revert.
- **Specialist**: no matching specialised agent — generalist (Orchestrator, Repo-Admin-API)
- **Depends on**: Merge des PRs

### P5 — Folge-Issue: unbeobachtete Inline-pip-Pins

- **Acceptance criteria**: Issue angelegt, nennt alle Fundstellen (`build-static-tests.yaml:88,99,112,125`, `reusable-sphinx.yaml:51`, neu `reusable-pre-commit.yaml`) und die Messung (keine Renovate-Commits, kein passender customManager); im PR unter Risk / rollout notes referenziert.
- **Specialist**: no matching specialised agent — generalist (Orchestrator)
- **Depends on**: none

## Dependency ordering

P1 → P2 → P3 → PR → (Merge) → P4 ; P5 unabhängig (vor PR-Erstellung, damit referenzierbar)

## Class sweep (Defektklasse)

- **Klasse**: Action-Referenz ohne vollen Commit-SHA, inkl. verschachtelt in Composite-Actions.
- **Guard (G1/G3/G6)**: das Repo-Setting `sha_pinning_required` selbst — mechanisch, deckt die ganze Klasse (alle Actions, rekursiv) ab, nicht nur die gemeldete Stelle. P4 schaltet ihn scharf.
- **Predicate**: Nested-Scan über alle externen `uses:` → vor Fix 1 Treffer, nach Fix erwartet 0.

## Risks

- **Cache-Key-Drift** → Consumer verlieren ihren Cache einmalig. Mitigation: Key wörtlich übernehmen.
- **Verhalten bei Consumern ändert sich** (pre-commit-Version nun gepinnt statt latest). Mitigation: 4.5.0 = aktuelle Version in requirements-dev; im PR als Rollout-Hinweis.
- **Setting bricht andere Lanes** (Release-, Schedule-Pfade). Mitigation: Scan zeigt 0 weitere Treffer; P4 verifiziert, sofortiger Revert dokumentiert.
- Security-sensitiver Pfad (`.github/workflows/`) → `cicd-pipeline-reviewer` + `security-review` vor PR (P3).

## Open questions

none

## Findings

| Finding | Source | Outcome | Reproduction | Issue |
|---|---|---|---|---|
| Inline-pip-Pins in Workflows werden von Renovate nicht verfolgt | Research (Renovate-Config + git log) | filed (P5) | `customManagers` in `renovate-configs/common.json`; `git log -S'pytest=='` | #467 |

## Dispatch log

2026-11-17 P5 handled by orchestrator — filed #467
2026-11-17 P1 dispatched to nolte-engineering:fullstack-developer — 4 direct steps, all uses SHA-pinned, cache key verbatim; actionlint 1.7.12 exit 0, yaml parse exit 0; orchestrator added #467 reference
2026-11-17 P2 dispatched to nolte-shared:prose-vale-curator — EN/DE L5+L33 updated; vale 3.15.2 on changed EN lines: 0 errors, 2 suggestions (1 new: Microsoft.Acronyms SHA; L33 SentenceLength pre-existing)
