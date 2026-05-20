# Portfolio GitHub App

Centralised GitHub App that lets reusable workflows in this repository
emit events GitHub considers user-initiated. Without it, three workflow
chains in the portfolio fail to cascade silently—`release-drafter`
after the `automerge` workflow runs, `release-cd-refresh-master` after
`release-publish`, and `build-static-tests` on the develop tip after
`automerge`.

Tracking issue: [#330](https://github.com/nolte/gh-plumbing/issues/330).
Spec reference: `spec/project/workflow-health/` §Known platform constraints.

---

## Why it exists

GitHub Actions has a deterministic platform constraint: workflow events
emitted under the default `GITHUB_TOKEN` don't trigger downstream
workflow runs. The reusable workflows in `nolte/gh-plumbing` that
perform downstream-relevant writes—squash-merging in
`reusable-automerge.yaml`, flipping a release to published in
`reusable-release-publish.yml`—therefore need a credential that
GitHub treats as user-initiated.

The spec mandates a portfolio-level remediation: one App, installed in
every consumer repository, with the same wrapper pattern in each
repository's `.github/workflows/`. No per-repository PAT collection,
no person-bound credential.

---

## Permissions the App requires

When you register the App, grant exactly these repository permissions:

| Permission | Scope | Why |
|---|---|---|
| `Contents` | `Read & write` | squash-merge to develop, edit releases, fast-forward master |
| `Pull requests` | `Read & write` | `pascalgn/automerge-action` reads and merges PRs |
| `Actions` | `Read` | `release-publish` reads `gh run list` for the post-publish cascade sanity check |
| `Metadata` | `Read` | mandatory baseline |

Nothing else. In particular: no `Administration` permission (the
repository-settings App is a separate service), no `Workflows`
permission (only needed if the App edits `.github/workflows/` files).

A webhook isn't required—the App is consumed exclusively from
workflow runs that mint an installation token at job start.

---

## Provisioning checklist

1. **Register the App** at
   `https://github.com/organizations/<org>/settings/apps/new` (or
   `https://github.com/settings/apps/new` for a personal account).
   Name suggestion: `nolte-portfolio-bot`.
2. **Grant the permissions listed earlier** and disable every webhook event.
3. **Generate a private key** (PEM). Save it once because GitHub doesn't
   show it again.
4. **Note the App ID** (visible on the App's settings page).
5. **Install the App** in every consumer repository that needs
   cascade-correct workflows. Start with `nolte/gh-plumbing` itself.
6. **Set repository (or organisation) credentials** on each consumer
   that adopts the App:
   - Variable `PORTFOLIO_APP_ID` (organisation- or repository-level
     [Actions variable](https://docs.github.com/en/actions/learn-github-actions/variables)).
     The App ID isn't sensitive; storing it as a variable lets the
     wrapper `if:` condition detect adoption.
   - Secret `PORTFOLIO_APP_PRIVATE_KEY` (organisation- or repository-level
     [Actions secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets))
     holding the full PEM contents from step 3.

---

## Wrapper pattern (for downstream consumers)

The two cascade-emitting wrappers in `nolte/gh-plumbing` show the
pattern. Copy the same shape into your repository for any wrapper
calling a `reusable-*.yaml` whose work should trigger downstream
workflows.

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

Key properties:

- **Backwards-compatible.** When `vars.PORTFOLIO_APP_ID` is unset, the
  mint step skips and the wrapper falls through to `github.token`
  (= `GITHUB_TOKEN`). Behaviour for consumers that haven't adopted the
  App is unchanged from the pre-App world.
- **Reusable workflows stay token-type-agnostic.** The reusable
  workflows in `nolte/gh-plumbing` accept any token shape; only the
  wrapper decides whether to use the App.
- **Short token lifetime.** `actions/create-github-app-token@v2`
  generates a one-hour installation token, scoped to the calling
  repository. No long-lived credential leaves GitHub's control plane.

!!! note "Only emitting wrappers need it"
    Wrappers that emit cascade-relevant events need the mint pattern:
    `automerge.yaml`, `release-publish.yml`. Wrappers that only consume
    cascade events (`release-drafter.yml`, `release-cd-refresh-master.yml`,
    `release-cd-deliver-docs.yml`) keep using `GITHUB_TOKEN`.

---

## Verification

After provisioning and adoption, both cascade chains should self-trigger:

| Action | Expected cascade |
|---|---|
| Apply `automerge` label to a green PR | `automerge.yaml` squash-merges → `release-drafter.yml` updates the draft → `build-static-tests.yaml` runs on the new develop tip |
| Dispatch `release-publish.yml` for an open draft | `reusable-release-publish.yml` flips draft=false → `release-cd-refresh-master.yml` fast-forwards master → `release-cd-deliver-docs.yml` rebuilds the mkdocs site |

If a cascade still fails to fire, check:

1. The App is installed in the consumer repository (`Settings → GitHub Apps`).
2. `vars.PORTFOLIO_APP_ID` is visible to the workflow (repository or
   organisation variable scope matches the workflow's repository).
3. The wrapper run shows the `mint-token` job as `success` with the
   `app-token` step executed (not skipped). A skipped step means the
   fallback path took over (`GITHUB_TOKEN` = cascade gap).

---

## Secret and key rotation

| Trigger | Action |
|---|---|
| Routine annual rotation | Generate a new private key on the App page, update `PORTFOLIO_APP_PRIVATE_KEY` in every consumer (or at organisation level once if organisation-scoped), delete the old key from the App. |
| Suspected key leak | Revoke the leaked key immediately from the App settings, generate a new one, distribute the same day. App ID stays unchanged. |
| App-ID rotation | Never needed because App IDs are immutable. |
| Permission scope change | Edit the App's permissions; existing installation tokens with old permissions continue to work for their TTL (≤ 1 h), then renew with new scope. |

---

## Branch-protection bypass (future work)

The spec also calls for the App to be declared as a branch-protection
bypass actor in `commons-settings.yml` so that the workflow-driven
primary path of
`spec/project/release-automation/` §Version-bearing file alignment
becomes usable. That change wires the App into every consumer's
`develop` and `master` branch protection through `_extends`.

It's intentionally **not** part of this initial PR. A separate PR
lands the bypass entry once the App is registered and you can fill in
its App slug.

---

## Related work

- Tracking issue: [#330](https://github.com/nolte/gh-plumbing/issues/330)
- PR introducing the wrapper pattern in `nolte/gh-plumbing`
- Earlier escape hatch for the `release-publish` cascade gap:
  [#329](https://github.com/nolte/gh-plumbing/pull/329)
- Spec sections: `spec/project/workflow-health/` §Known platform
  constraints, `spec/project/release-automation/` §Permissions and
  protection
