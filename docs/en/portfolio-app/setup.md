# Portfolio app

Centralised GitHub App that lets reusable workflows in this repository
emit events GitHub considers user-initiated. Without it, three workflow
chains in the portfolio fail to cascade—`release-drafter` after the
`automerge` workflow runs, `release-cd-refresh-master` after
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
repository's `.github/workflows/`. No per-repository
Personal-Access-Token collection, no person-bound credential.

---

## Owner modes

The portfolio App can serve consumers under a GitHub **organisation**
or under a personal **user** account. Pick the mode that matches the
account that owns the consumer repositories. Both modes give the same
downstream behaviour: App-authored events cascade user-initiated.
Only the credential plumbing differs.

| Mode | When to pick | Credentials live as |
|---|---|---|
| Organisation mode | The account owning consumer repositories is a GitHub organisation. Cheaper to operate when three or more consumers exist. | One organisation-level Actions variable + one organisation-level Actions secret with `visibility = "selected"` scoped to the consumer-repositories list. |
| User mode | The account owning consumer repositories is a personal GitHub account (no organisation). | One repository-level Actions variable + one repository-level Actions secret on each consumer repository. |

Both modes use the same wrapper pattern in `.github/workflows/`. The
wrappers don't care which mode set their `PORTFOLIO_APP_ID` /
`PORTFOLIO_APP_PRIVATE_KEY` pair, only that the pair resolves to a
valid App at job start.

---

## Permissions the app requires

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

A webhook isn't required—workflow runs that mint an installation
token at job start use the App exclusively.

---

## Provisioning checklist

1. **Register the App** at
   `https://github.com/organizations/<org>/settings/apps/new` (or
   `https://github.com/settings/apps/new` for a personal account).
   Name suggestion: `nolte-portfolio-bot`.
2. **Grant the permissions listed earlier** and disable every webhook event.
3. **Generate a private key** in Privacy-Enhanced-Mail format. Save it
   once because GitHub doesn't show it again.
4. **Note the App ID** (visible on the App's settings page).
5. **Install the App** in every consumer repository that needs
   cascade-correct workflows. Start with `nolte/gh-plumbing` itself.
6. **Set credentials** at the scope that matches the owner mode:
   - **Organisation mode:** one
     [organisation-level Actions variable](https://docs.github.com/en/actions/learn-github-actions/variables)
     `PORTFOLIO_APP_ID` and one
     [organisation-level Actions secret](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
     `PORTFOLIO_APP_PRIVATE_KEY`, both with `visibility = "selected"`
     scoped to the consumer-repositories list.
   - **User mode:** one repository-level Actions variable
     `PORTFOLIO_APP_ID` and one repository-level Actions secret
     `PORTFOLIO_APP_PRIVATE_KEY` on **every** consumer repository.
     Personal accounts don't expose org-level Actions resources, so
     each repository carries its own pair.

   The App ID isn't sensitive. Storing it as a variable lets the
   wrapper `if:` condition detect adoption. The private-key contents
   from step 3 go into the secret.

!!! tip "Terraform-driven provisioning"
    Steps 5 and 6 are also available as a Terraform module under
    [`terraform/portfolio-app/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app).
    The module supports both organisation and user mode, creates the
    variable and secret in one `terraform apply`, and (optionally)
    declares the App as a branch-protection bypass actor. Steps 1–4
    stay manual because GitHub provides no API to create an App. See
    [`examples/basic/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app/examples/basic)
    for organisation mode and
    [`examples/personal-account/`](https://github.com/nolte/gh-plumbing/tree/develop/terraform/portfolio-app/examples/personal-account)
    for user mode.

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
  automerge:
    uses: nolte/gh-plumbing/.github/workflows/reusable-automerge.yaml@develop
    with:
      app-id: ${{ vars.PORTFOLIO_APP_ID }}
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}
      app-private-key: ${{ secrets.PORTFOLIO_APP_PRIVATE_KEY }}
```

Key properties:

- **Backwards-compatible.** When `vars.PORTFOLIO_APP_ID` is unset, the
  reusable skips the mint step and falls through to `secrets.token`
  (= `GITHUB_TOKEN`). Consumers that haven't adopted the App see no
  behaviour change from the pre-App world.
- **Mint happens inside the reusable.** GitHub Actions masks App-token
  outputs and blocks them from crossing job boundaries, so a separate
  mint job in the wrapper can't pass the token to a downstream
  reusable call. The reusable holds the mint step itself, gated on
  `inputs.app-id`.
- **Short token lifetime.** `actions/create-github-app-token@v2`
  generates a one-hour installation token, scoped to the calling
  repository. No long-lived credential leaves the GitHub control plane.

!!! note "Only emitting wrappers need it"
    Wrappers that emit cascade-relevant events need the App-credential
    forwarding pattern: `automerge.yaml`, `release-publish.yml`.
    Wrappers that only consume cascade events (`release-drafter.yml`,
    `release-cd-refresh-master.yml`, `release-cd-deliver-docs.yml`)
    keep using `GITHUB_TOKEN`.

---

## Verification

After provisioning and adoption, both cascade chains should self-trigger:

| Action | Expected cascade |
|---|---|
| Apply `automerge` label to a green PR | `automerge.yaml` squash-merges → `release-drafter.yml` updates the draft → `build-static-tests.yaml` runs on the new develop tip |
| Dispatch `release-publish.yml` for an open draft | `reusable-release-publish.yml` flips draft=false → `release-cd-refresh-master.yml` fast-forwards master → `release-cd-deliver-docs.yml` rebuilds the mkdocs site |

If a cascade still fails to fire, check:

1. Confirm the App install in the consumer repository (`Settings → GitHub Apps`).
2. Confirm `vars.PORTFOLIO_APP_ID` is visible to the workflow.
   Organisation mode: the org-level variable's `visibility = "selected"`
   list includes the workflow's repository. User mode: the repository
   carries its own `PORTFOLIO_APP_ID` Actions variable.
3. The reusable run shows the `Mint App installation token` step as
   `success`, not `skipped`. A skipped step means the App-id input
   arrived empty and the fallback path took over (`GITHUB_TOKEN` =
   cascade gap).

---

## Secret and key rotation

| Trigger | Action |
|---|---|
| Routine annual rotation | Generate a new private key on the App page, update `PORTFOLIO_APP_PRIVATE_KEY` in every consumer (or at organisation level once if organisation-scoped), delete the old key from the App. |
| Suspected key leak | Revoke the leaked key immediately from the App settings, generate a new one, distribute the same day. App ID stays unchanged. |
| App-ID rotation | Never needed because App IDs are immutable. |
| Permission scope change | Edit the App's permissions; existing installation tokens with old permissions continue to work for their time-to-live (≤ 1 h), then renew with new scope. |

---

## Branch-protection bypass (future work)

The spec also calls for declaring the App as a branch-protection
bypass actor in `commons-settings.yml` so that the workflow-driven
primary path of
`spec/project/release-automation/` §Version-bearing file alignment
becomes usable. That change wires the App into every consumer's
`develop` and `master` branch protection through `_extends`.

This change isn't part of the initial PR. A separate PR lands
the bypass entry once you have the App registered and can fill in
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
