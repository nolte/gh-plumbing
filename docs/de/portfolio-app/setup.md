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
`.github/workflows/`. Kein PAT-Sammeln pro Repo, kein
personengebundenes Credential.

---

## Owner-Modi

Die Portfolio-App kann Konsumenten unter einer GitHub-**Organisation**
oder unter einem persönlichen **User-Account** bedienen. Wähle den
Modus, der zum Account passt, der die Konsumenten-Repositories
besitzt — beide Modi liefern dasselbe nachgelagerte Verhalten
(App-emittierte Events kaskadieren user-initiated), nur die
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

Bei der Registrierung exakt diese Repository-Permissions vergeben:

| Permission | Scope | Wofür |
|---|---|---|
| `Contents` | `Read & write` | Squash-Merge nach develop, Releases editieren, master fast-forwarden |
| `Pull requests` | `Read & write` | `pascalgn/automerge-action` liest und merged PRs |
| `Actions` | `Read` | `release-publish` liest `gh run list` für den Post-Publish-Cascade-Check |
| `Metadata` | `Read` | Pflicht-Basis |

Sonst nichts. Insbesondere: keine `Administration`-Permission (die
Repository-Settings-App ist ein eigenständiger Service), keine
`Workflows`-Permission (nur nötig, wenn die App Dateien unter
`.github/workflows/` editiert).

Webhook wird nicht gebraucht — die App wird ausschließlich aus
Workflow-Runs konsumiert, die zu Beginn eines Jobs ein
Installation-Token holen.

---

## Provisionierungs-Checkliste

1. **App registrieren** unter
   `https://github.com/organizations/<org>/settings/apps/new` (bzw.
   `https://github.com/settings/apps/new` für einen persönlichen
   Account). Namensvorschlag: `nolte-portfolio-bot`.
2. **Permissions wie oben vergeben** und jeden Webhook-Event abwählen.
3. **Private Key (PEM) generieren** — einmal speichern; GitHub zeigt
   ihn nicht erneut an.
4. **App-ID notieren** (sichtbar auf der App-Settings-Seite).
5. **App installieren** in jedem Konsument-Repository, das
   cascade-korrekte Workflows braucht. Beginne mit
   `nolte/gh-plumbing` selbst.
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

Die beiden Cascade-emittierenden Wrapper in `nolte/gh-plumbing` zeigen
das Pattern. Übernimm dieselbe Form in dein Repository für jeden
Wrapper, der eine `reusable-*.yaml` aufruft, deren Arbeit nachgelagerte
Workflows triggern soll.

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
  mint-token:
    runs-on: ubuntu-latest
    outputs:
      token: ${{ steps.app-token.outputs.token || github.token }}
    steps:
      - id: app-token
        if: ${{ vars.PORTFOLIO_APP_ID != '' }}
        uses: actions/create-github-app-token@v2
        with:
          app-id: ${{ vars.PORTFOLIO_APP_ID }}
          private-key: ${{ secrets.PORTFOLIO_APP_PRIVATE_KEY }}

  automerge:
    needs: mint-token
    uses: nolte/gh-plumbing/.github/workflows/reusable-automerge.yaml@develop
    secrets:
      token: ${{ needs.mint-token.outputs.token }}
```

Schlüsseleigenschaften:

- **Backwards-kompatibel.** Wenn `vars.PORTFOLIO_APP_ID` ungesetzt ist,
  überspringt der Mint-Step und der Wrapper fällt zurück auf
  `github.token` (= `GITHUB_TOKEN`). Das Verhalten für nicht-adoptierte
  Konsumenten ist identisch zum Pre-App-Zustand.
- **Reusables bleiben tokentyp-agnostisch.** Die Reusables in
  `nolte/gh-plumbing` akzeptieren jede Token-Form; nur der Wrapper
  entscheidet, ob die App zum Zug kommt.
- **Kurze Token-Lebensdauer.**
  `actions/create-github-app-token@v2` erzeugt ein 1-Stunden-Installation-Token,
  begrenzt auf das aufrufende Repository. Es verlässt nie GitHubs
  Control Plane als langlebiges Credential.

!!! note "Nur emittierende Wrapper brauchen das Pattern"
    Wrapper, die Cascade-relevante Events emittieren, brauchen den
    Mint-Pattern: `automerge.yaml`, `release-publish.yml`. Wrapper, die
    nur Cascade-Events konsumieren (`release-drafter.yml`,
    `release-cd-refresh-master.yml`, `release-cd-deliver-docs.yml`),
    nutzen weiter `GITHUB_TOKEN`.

---

## Verifikation

Nach Provisionierung und Adoption sollten beide Cascade-Ketten von
selbst triggern:

| Aktion | Erwarteter Cascade |
|---|---|
| `automerge`-Label an einen grünen PR | `automerge.yaml` squash-merged → `release-drafter.yml` aktualisiert den Entwurf → `build-static-tests.yaml` läuft auf dem neuen develop-Tip |
| `release-publish.yml` für offenen Entwurf dispatchen | `reusable-release-publish.yml` flippt draft=false → `release-cd-refresh-master.yml` fast-forwarded master → `release-cd-deliver-docs.yml` baut die MkDocs-Site neu |

Wenn ein Cascade immer noch nicht triggert, prüfe:

1. Die App ist im Konsument-Repo installiert (`Settings → GitHub Apps`).
2. `vars.PORTFOLIO_APP_ID` ist für den Workflow sichtbar.
   Organisations-Modus: die Org-Variable hat `visibility = "selected"`
   inklusive des Workflow-Repos. User-Modus: das Repository trägt
   seine eigene `PORTFOLIO_APP_ID`-Actions-Variable.
3. Der reusable-Run zeigt den `Mint App installation token`-Step als
   `success` (nicht `skipped`). Skipped Step bedeutet, der App-ID-Input
   war leer und der Fallback-Pfad griff (`GITHUB_TOKEN` =
   Cascade-Lücke).

---

## Secret- und Key-Rotation

| Trigger | Aktion |
|---|---|
| Reguläre jährliche Rotation | Neuen Private Key auf der App-Seite generieren, `PORTFOLIO_APP_PRIVATE_KEY` in jedem Konsumenten aktualisieren (oder einmal auf Org-Level, falls org-scoped), den alten Key auf der App-Seite löschen. |
| Vermuteter Key-Leak | Geleakten Key sofort in den App-Settings widerrufen, neuen Key generieren, am selben Tag verteilen. App-ID bleibt unverändert. |
| App-ID-Rotation | Niemals nötig — App-IDs sind unveränderlich. |
| Permission-Scope-Änderung | App-Permissions editieren; bestehende Installation-Tokens mit alten Permissions laufen für ihre TTL (≤ 1 h) weiter, dann werden sie mit neuem Scope erneuert. |

---

## Branch-Protection-Bypass (Folgearbeit)

Die Spec verlangt außerdem, die App in `commons-settings.yml` als
Bypass-Actor für Branch-Protection zu deklarieren, damit der
workflow-getriebene Primary Path aus
`spec/project/release-automation/` §Version-bearing file alignment
nutzbar wird. Diese Änderung verdrahtet die App über `_extends` in die
`develop`- und `master`-Branch-Protection jedes Konsumenten.

Sie ist absichtlich **nicht** Teil dieses initialen PRs. Ein separater
PR fügt den Bypass-Eintrag ein, sobald die App registriert ist und du
ihren App-Slug eintragen kannst.

---

## Verwandte Arbeit

- Tracking-Issue: [#330](https://github.com/nolte/gh-plumbing/issues/330)
- PR, der das Wrapper-Pattern in `nolte/gh-plumbing` einführt
- Frühere Escape-Hatch für die release-publish-Cascade-Lücke:
  [#329](https://github.com/nolte/gh-plumbing/pull/329)
- Spec-Sektionen: `spec/project/workflow-health/` §Known platform
  constraints, `spec/project/release-automation/` §Permissions and
  protection
