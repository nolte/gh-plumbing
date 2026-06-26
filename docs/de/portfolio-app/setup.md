# Portfolio-GitHub-App

Zentral verwaltete GitHub App, die es den wiederverwendbaren Workflows
dieses Repositories erlaubt, Events zu emittieren, die GitHub als
user-initiated betrachtet. Ohne sie scheitern drei Workflow-Ketten im
Portfolio still: `release-drafter` nach Automerge,
`release-cd-refresh-master` nach `release-publish` und
`build-static-tests` auf dem develop-Tip nach Automerge.

Tracking-Issue: [#330](https://github.com/nolte/gh-plumbing/issues/330).
Spec-Referenz: `spec/project/workflow-health/` §Known platform constraints.

---

## Warum die App existiert

GitHub Actions hat eine deterministische Plattform-Einschränkung:
Workflow-Events, die unter dem default `GITHUB_TOKEN` emittiert werden,
triggern keine nachgelagerten Workflow-Runs. Die reusable Workflows in
`nolte/gh-plumbing`, die nachgelagert relevante Writes ausführen — der
Squash-Merge in `reusable-automerge.yaml`, das Flippen eines Releases
auf `published` in `reusable-release-publish.yml` — brauchen daher ein
Credential, das GitHub als user-initiated wertet.

Die Spec verlangt eine Portfolio-Level-Lösung: eine App, in jedem
Konsument-Repo installiert, mit demselben Wrapper-Pattern in jedem
`.github/workflows/`. Kein Sammeln von Personal-Access-Tokens (PAT)
pro Repo, kein personengebundenes Credential.

---

## Owner-Modi

Die Portfolio-App kann Konsumenten unter einer GitHub-**Organisation**
oder unter einem persönlichen **User-Account** bedienen. Den Modus
wählen, der zum Account passt, der die Konsumenten-Repositories
besitzt. Beide Modi liefern dasselbe nachgelagerte Verhalten —
App-emittierte Events kaskadieren user-initiated —, nur die
Credential-Verkabelung unterscheidet sich.

| Modus | Wann wählen | Credentials liegen als |
|---|---|---|
| Organisations-Modus | Der Account, der die Konsumenten-Repositories besitzt, ist eine GitHub-Organisation. Günstiger im Betrieb ab drei Konsumenten. | Eine Org-Level-Actions-Variable + ein Org-Level-Actions-Secret mit `visibility = "selected"`, beschränkt auf die Konsumenten-Liste. |
| User-Modus | Der Account, der die Konsumenten-Repositories besitzt, ist ein persönlicher GitHub-Account (keine Org). | Eine Repo-Level-Actions-Variable + ein Repo-Level-Actions-Secret in jedem Konsumenten-Repository. |

Beide Modi nutzen dasselbe Wrapper-Pattern in `.github/workflows/`;
die Wrapper interessiert nicht, welcher Modus ihr
`PORTFOLIO_APP_ID` / `PORTFOLIO_APP_PRIVATE_KEY`-Paar gesetzt hat,
sondern nur, dass das Paar zum Job-Start eine gültige App ergibt.

---

## Welche Permissions die App braucht

Bei der Registrierung exakt diese **Repository permissions**
vergeben:

| Permission | Scope | Wofür |
|---|---|---|
| `Contents` | `Read and write` | Squash-Merge nach develop, Releases editieren, master fast-forwarden |
| `Pull requests` | `Read and write` | `pascalgn/automerge-action` liest und merged PRs |
| `Issues` | `Read and write` | Auto-Close von Issues, die im PR-Body via `Closes #N` / `Fixes #N` / `Resolves #N` referenziert sind, wenn die App den Squash-Merge ausführt. GitHub schließt referenzierte Issues nur, wenn der mergende Actor `Issues: write` hat — fehlt diese Permission, parst GitHub die Autolinks zwar in `closingIssuesReferences`, aber der Close-Flip feuert nicht (Live-Beobachtung an #357 / #358). |
| `Actions` | `Read-only` | `release-publish` liest `gh run list` für den Post-Publish-Cascade-Check |
| `Metadata` | `Read-only` | Pflicht-Basis (setzt GitHub automatisch und lässt sich nicht abwählen) |

**Jede andere Repository-Permission** bleibt auf `No access`,
insbesondere die zwei, die verwandt klingen, aber keine sind:

| Permission | Setting | Wieso NICHT |
|---|---|---|
| `Administration` | `No access` | Die Probot Settings App verwaltet Repo-Konfiguration. Diese Permission hier zu setzen erhöht nur die Angriffsfläche, ohne Nutzen. |
| `Workflows` | `No access` | Würde der App erlauben, `.github/workflows/*.yaml` zu überschreiben. Unsere Use-Case merged Branches und Releases, keine Workflow-Dateien. Später aktivieren, falls jemals nötig. |

**Alle Organization permissions** und **alle Account permissions**
bleiben auf `No access` — die Arbeit der App ist repo-scoped.

### Identifying and authorizing users

Diese ganze Sektion bleibt aus. Unsere App agiert über
Installation-Tokens, die in Workflow-Runs gemintet werden, niemals
im Namen eines Endnutzers:

- **Callback URL** bleibt leer (`Delete` auf den Platzhalter klicken).
- **Request user authorization (OAuth) during installation** bleibt
  ungesetzt.
- **Enable Device Flow** bleibt ungesetzt.
- **Expire user authorization tokens** ist egal; GitHub setzt es
  vor, aber wir geben keine User-Tokens aus, die ablaufen könnten.

### Webhook

Webhook komplett deaktivieren (**Active** abwählen). Die App wird
ausschließlich aus Workflow-Runs konsumiert, die zu Beginn eines
Jobs ein Installation-Token holen — keine Event-Subscriptions
notwendig und kein Endpoint vorhanden, der sie entgegennimmt.

### Subscribe to events

In der Event-Liste der App **keinen einzigen Event** abonnieren.
Jedes aktivierte Häkchen würde nur tote Webhook-Versuche erzeugen.

---

## Provisionierungs-Checkliste

1. **App registrieren** unter
   `https://github.com/organizations/<org>/settings/apps/new` (bzw.
   `https://github.com/settings/apps/new` für einen persönlichen
   Account). Namensvorschlag: `nolte-portfolio-bot`.
2. **Permissions wie oben vergeben** und jeden Webhook-Event abwählen.
3. **Private Key im PEM-Format (Privacy-Enhanced Mail) generieren** —
   einmal speichern; GitHub zeigt ihn nicht erneut an.
4. **App-ID notieren** (sichtbar auf der App-Settings-Seite).
5. **App installieren** in jedem Konsument-Repository, das
   cascade-korrekte Workflows braucht. Mit `nolte/gh-plumbing` selbst
   beginnen.
6. **Credentials setzen** im Scope, der zum Owner-Modus passt:
   - **Organisations-Modus:** eine
     [Org-Level-Actions-Variable](https://docs.github.com/en/actions/learn-github-actions/variables)
     `PORTFOLIO_APP_ID` und ein
     [Org-Level-Actions-Secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
     `PORTFOLIO_APP_PRIVATE_KEY`, beide mit `visibility = "selected"`
     auf die Konsumenten-Liste eingeschränkt.
   - **User-Modus:** eine Repo-Level-Actions-Variable
     `PORTFOLIO_APP_ID` und ein Repo-Level-Actions-Secret
     `PORTFOLIO_APP_PRIVATE_KEY` in **jedem** Konsumenten-Repository.
     Persönliche Accounts bieten keine Org-Level-Actions-Resourcen,
     daher trägt jedes Repository sein eigenes Paar.

   Die App-ID ist nicht sensibel; als Variable abgelegt kann die
   `if:`-Condition im Wrapper die Adoption erkennen. Der
   Private-Key-Inhalt aus Schritt 3 landet im Secret.

!!! tip "Terraform-getriebene Provisionierung"
    Die Schritte 5 und 6 sind auch als Terraform-Modul unter
    [`terraform/portfolio-app/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app)
    verfügbar. Das Modul unterstützt beide Modi (Organisation und
    User), legt Variable und Secret in einem `terraform apply` an und
    deklariert optional die App als Branch-Protection-Bypass-Actor.
    Schritte 1–4 bleiben manuell, weil GitHub keine API zur
    App-Erstellung anbietet. Siehe
    [`examples/basic/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app/examples/basic)
    für den Organisations-Modus und
    [`examples/personal-account/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app/examples/personal-account)
    für den User-Modus.

---

## Wrapper-Pattern (für nachgelagerte Konsumenten)

Die Cascade-emittierenden Wrapper in `nolte/gh-plumbing` zeigen das
Pattern. Dieselbe Form in das eigene Repository für jeden Wrapper
übernehmen, der eine `reusable-*.yaml` aufruft, deren Arbeit
nachgelagerte Workflows triggern soll oder die unter derselben
Release-Audit-Identität bleiben soll.

```yaml title=".github/workflows/automerge.yaml"
on:
  pull_request:
    types: [labeled, unlabeled, synchronize, opened, edited, ready_for_review, reopened, unlocked]
  pull_request_review:
    types: [submitted]
  check_suite:
    types: [completed]
  status: {}

jobs:
  automerge:
    uses: nolte/gh-plumbing/.github/workflows/reusable-automerge.yaml@develop
    with:
      app-id: ${{ vars.PORTFOLIO_APP_ID }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
      app-private-key: ${{ secrets.PORTFOLIO_APP_PRIVATE_KEY }}
```

Schlüsseleigenschaften:

- **Backwards-kompatibel.** Wenn `vars.PORTFOLIO_APP_ID` ungesetzt ist,
  überspringt der Reusable den Mint-Step und fällt zurück auf
  `secrets.token` (= `GITHUB_TOKEN`). Das Verhalten für
  nicht-adoptierte Konsumenten ist identisch zum Pre-App-Zustand.
- **Mint passiert im Reusable.** GitHub Actions maskiert
  App-Token-Outputs und blockiert sie an Job-Grenzen — ein separater
  Mint-Job im Wrapper kann das Token nicht an einen nachgelagerten
  Reusable-Call weitergeben. Der Reusable hält den Mint-Step selbst,
  gated auf `inputs.app-id`.
- **Kurze Token-Lebensdauer.**
  `actions/create-github-app-token@v2` erzeugt ein 1-Stunden-Installation-Token,
  begrenzt auf das aufrufende Repository. Es verlässt nie GitHubs
  Control Plane als langlebiges Credential.

!!! note "Fünf Wrapper brauchen das App-Credential-Forwarding"
    Drei Wrapper pushen durch einen geschützten Branch und **müssen**
    das App-Token-Pattern verwenden:

    - `automerge.yaml` (Squash-Merge nach `develop`).
    - `release-publish.yml` (Release-Flip — emittiert
      `release: published` und kaskadiert weiter).
    - `release-cd-refresh-master.yml` (Fast-Forward nach `master`, das
      nach Phase 2 ebenfalls push-restricted ist).

    Zwei weitere Wrapper reichen dasselbe Credential aus
    Konsistenz- und Audit-Trail-Gründen durch, obwohl ihr Ziel-Branch
    nicht geschützt ist:

    - `release-drafter.yml` aktualisiert den Release-Entwurf über die
      GitHub-API. Unter dem Portfolio-App-Token läuft jeder
      Release-Toolchain-Schritt unter einer einheitlichen Identität.
    - `release-cd-deliver-docs.yml` pusht die gerenderte Site nach
      `gh-pages`. `gh-pages` hat keine Protection — das App-Token ist
      hier rein Audit-Trail-Verbesserung.

    Alle fünf Wrapper bleiben backwards-kompatibel: ist
    `vars.PORTFOLIO_APP_ID` ungesetzt, fällt jeder Reusable auf
    `GITHUB_TOKEN` zurück und funktioniert weiter.

---

## Verifikation

Nach Provisionierung und Adoption sollten beide Cascade-Ketten von
selbst triggern:

| Aktion | Erwarteter Cascade |
|---|---|
| `automerge`-Label an einen grünen PR | `automerge.yaml` squash-merged → `release-drafter.yml` aktualisiert den Entwurf → `build-static-tests.yaml` läuft auf dem neuen develop-Tip |
| `release-publish.yml` für offenen Entwurf dispatchen | `reusable-release-publish.yml` flippt draft=false → `release-cd-refresh-master.yml` fast-forwarded master → `release-cd-deliver-docs.yml` baut die MkDocs-Site neu |

Eine dritte Self-Check-Zeile betrifft den Issue-Lifecycle:

| Aktion | Erwartetes Ergebnis |
|---|---|
| PR squash-mergen, dessen Body `Closes #N` enthält | Issue `#N` flippt automatisch auf `CLOSED`; `gh issue view N --json state` liefert `CLOSED`. Setzt die App-Permission `Issues: Read and write` voraus — ohne sie greift der Merge zwar, der Close feuert aber nicht, obwohl `gh pr view --json closingIssuesReferences` den Autolink korrekt geparst zeigt. |

Wenn ein Cascade immer noch nicht triggert, prüfen:

1. Die App ist im Konsument-Repo installiert (`Settings → GitHub Apps`).
2. `vars.PORTFOLIO_APP_ID` ist für den Workflow sichtbar.
   Organisations-Modus: die Org-Variable hat `visibility = "selected"`
   inklusive des Workflow-Repos. User-Modus: das Repository trägt
   seine eigene `PORTFOLIO_APP_ID`-Actions-Variable.
3. Der reusable-Run zeigt den `Mint App installation token`-Step als
   `success` (nicht `skipped`). Skipped Step bedeutet, der App-ID-Input
   war leer und der Fallback-Pfad griff (`GITHUB_TOKEN` =
   Cascade-Lücke). Greift der Fallback-Pfad, trägt die Job-Summary des
   Runs eine explizite **"Cascade gap (GITHUB_TOKEN fallback)"**-Warnung,
   die auf den manuellen Fast-Forward-Notausgang hinweist.

---

## Secret- und Key-Rotation

| Trigger | Aktion |
|---|---|
| Reguläre jährliche Rotation | Neuen Private Key auf der App-Seite generieren, `PORTFOLIO_APP_PRIVATE_KEY` in jedem Konsumenten aktualisieren (oder einmal auf Org-Level, falls org-scoped), den alten Key auf der App-Seite löschen. |
| Vermuteter Key-Leak | Geleakten Key sofort in den App-Settings widerrufen, neuen Key generieren, am selben Tag verteilen. App-ID bleibt unverändert. |
| App-ID-Rotation | Niemals nötig — App-IDs sind unveränderlich. |
| Permission-Scope-Änderung | App-Permissions editieren; bestehende Installation-Tokens mit alten Permissions laufen für ihre Gültigkeitsdauer (TTL, ≤ 1 h) weiter, dann werden sie mit neuem Scope erneuert. |

---

## Branch-Protection-Bypass (Phase 2)

`commons-settings.yml` deklariert die App als Push-Restriction-Actor
auf den Branches `develop` und `master`. Da Konsumenten-Repositories
die Commons per `_extends:` einbinden, propagiert der Bypass
automatisch zu jedem Adopter, sobald die App in dessen Repository
installiert ist.

Der konfigurierte Slug ist **`nolte-portfolio-app`**:

```yaml title=".github/commons-settings.yml"
branches:
  - name: develop
    protection:
      enforce_admins: true
      restrictions:
        users: []
        teams: []
        apps:
          - nolte-portfolio-app
```

Derselbe Block gilt für `master`.

!!! warning "Persönliche Accounts unterstützen `restrictions.apps` nicht"
    GitHub beschränkt `restrictions.users` / `.teams` / `.apps` auf
    Organisations-Repositories. Die Probot Settings App überspringt
    das Feld still, wenn es in einem persönlichen Account landet.
    Persönliche-Account-Konsumenten arbeiten entweder ohne
    Push-Restriktionen oder überschreiben den Branches-Block in
    ihrem per-Repo-`.github/settings.yml`.

!!! tip "Vorbedingung für Phase 2"
    Vor dem Merge des Phase-2-PRs muss die App bereits in jedem
    Konsumenten-Repository installiert sein, dessen
    `commons-settings.yml` den Bypass erhält. Eine nicht installierte
    App kann nichts bypassen; der einzige Effekt einer zu frühen
    Phase 2 wäre, direkte Pushes von allen anderen Actors zu
    blockieren.

---

## Verwandte Arbeit

- Tracking-Issue: [#330](https://github.com/nolte/gh-plumbing/issues/330)
- PR, der das Wrapper-Pattern in `nolte/gh-plumbing` einführt
- Frühere Escape-Hatch für die release-publish-Cascade-Lücke:
  [#329](https://github.com/nolte/gh-plumbing/pull/329)
- Spec-Sektionen: `spec/project/workflow-health/` §Known platform
  constraints, `spec/project/release-automation/` §Permissions and
  protection
