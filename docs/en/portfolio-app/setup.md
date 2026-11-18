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

When you register the App, grant exactly these **Repository
permissions**:

| Permission | Scope | Why |
|---|---|---|
| `Contents` | `Read and write` | Squash-merge to develop, edit releases, fast-forward master |
| `Pull requests` | `Read and write` | `pascalgn/automerge-action` reads and merges PRs |
| `Issues` | `Read and write` | Automatically close issues referenced via `Closes #N` / `Fixes #N` / `Resolves #N` in the PR body when the App squash-merges. GitHub only honours these closing references when the merging actor has `Issues: write`; without this scope the references parse correctly into `closingIssuesReferences` but the close never fires (observed end-to-end on #357 / #358). |
| `Actions` | `Read-only` | `release-publish` reads `gh run list` for the post-publish cascade sanity check |
| `Metadata` | `Read-only` | Mandatory baseline (GitHub sets this automatically and won't let you disable it) |

Leave **every other Repository permission** on `No access`, in
particular the two that look related but aren't:

| Permission | Setting | Reason to skip |
|---|---|---|
| `Administration` | `No access` | The Probot Settings App owns repository configuration. Granting this here adds attack surface for no gain. |
| `Workflows` | `No access` | Would let the App rewrite `.github/workflows/*.yaml`. The use case in this repository merges branches and releases, not workflow files. Add later only if a future reusable needs it. |

Leave **all Organization permissions** and **all Account permissions**
on `No access`. The App's work is repository-scoped.

### Identifying and authorizing users

Leave this entire section off. The App acts through installation
tokens minted in workflow runs, never on behalf of an end user:

- **Callback `URL`** stays empty (`Delete` the placeholder).
- **Request user authorization (`OAuth`) during installation** stays
  unchecked.
- **Enable Device Flow** stays unchecked.
- **Expire user authorization tokens** is irrelevant either way;
  GitHub pre-checks it, but the App issues no user tokens to expire.

### Webhook

Disable the webhook entirely (clear the **Active** checkbox). The App
runs exclusively inside workflow runs that mint an installation token
at job start. The App subscribes to no events and exposes no endpoint
to receive them.

### Subscribe to events

Subscribe to **no events** in the App's event list. Leaving any
subscription on would only generate dead webhook attempts.

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

The cascade-emitting wrappers in `nolte/gh-plumbing` show the
pattern. Copy the same shape into your repository for any wrapper
calling a `reusable-*.yaml` whose work should trigger downstream
workflows or that you want to keep under the same release-audit
identity.

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
    uses: nolte/gh-plumbing/.github/workflows/reusable-automerge.yaml@<tag>
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

!!! note "Five wrappers need the App-credential forwarding"
    Three wrappers push through a protected branch and **need** the
    App-token pattern:

    - `automerge.yaml` squash-merges to `develop`.
    - `release-publish.yml` flips the release to published. The
      resulting `release: published` event then cascades to other
      workflows.
    - `release-cd-refresh-master.yml` fast-forwards `master`. The
      commons don't restrict pushes to `master`; its own protection
      decides who may push
      ([ADR-006](../decisions/adr-006-consumer-owned-master-protection.md)).

    Two more wrappers forward the same credential for consistency and
    audit-trail homogeneity, even though their target branch isn't
    protected:

    - `release-drafter.yml` updates the draft release through the
      GitHub API. Running it under the portfolio-App token keeps every
      release-toolchain step under one identity.
    - `release-cd-deliver-docs.yml` pushes the rendered site to
      `gh-pages`. `gh-pages` has no protection, so the App token here
      is an audit-trail improvement only.

    All five wrappers stay backwards-compatible: when
    `vars.PORTFOLIO_APP_ID` is unset, each reusable falls through to
    `GITHUB_TOKEN` and keeps working.

---

## Verification

After provisioning and adoption, both cascade chains should self-trigger:

| Action | Expected cascade |
|---|---|
| Apply `automerge` label to a green PR | `automerge.yaml` squash-merges → `release-drafter.yml` updates the draft → `build-static-tests.yaml` runs on the new develop tip |
| Dispatch `release-publish.yml` for an open draft | `reusable-release-publish.yml` flips draft=false → `release-cd-refresh-master.yml` fast-forwards master → `release-cd-deliver-docs.yml` rebuilds the mkdocs site |

A third self-check covers the issue lifecycle:

| Action | Expected outcome |
|---|---|
| Squash-merge a PR whose body says `Closes #N` | Issue `#N` flips to `CLOSED` automatically; `gh issue view N --json state` returns `CLOSED`. Requires the App's `Issues: Read and write` permission—without it the merge succeeds but the close never fires, even though `gh pr view --json closingIssuesReferences` shows that GitHub parsed the link. |

If a cascade still fails to fire, check:

1. Confirm the App install in the consumer repository (`Settings → GitHub Apps`).
2. Confirm `vars.PORTFOLIO_APP_ID` is visible to the workflow.
   Organisation mode: the org-level variable's `visibility = "selected"`
   list includes the workflow's repository. User mode: the repository
   carries its own `PORTFOLIO_APP_ID` Actions variable.
3. The reusable run shows the `Mint App installation token` step as
   `success`, not `skipped`. A skipped step means the App-id input
   arrived empty and the fallback path took over (`GITHUB_TOKEN` =
   cascade gap). When the fallback path is taken the run's job summary
   carries an explicit **"Cascade gap (GITHUB_TOKEN fallback)"** warning
   that names the manual fast-forward escape hatch.

---

## Secret and key rotation

| Trigger | Action |
|---|---|
| Routine annual rotation | Generate a new private key on the App page, update `PORTFOLIO_APP_PRIVATE_KEY` in every consumer (or at organisation level once if organisation-scoped), delete the old key from the App. |
| Suspected key leak | Revoke the leaked key immediately from the App settings, generate a new one, distribute the same day. App ID stays unchanged. |
| App-ID rotation | Never needed because App IDs are immutable. |
| Permission scope change | Edit the App's permissions; existing installation tokens with old permissions continue to work for their time-to-live (≤ 1 h), then renew with new scope. |

---

## Branch-protection bypass (phase 2)

Phase 2 declared the App as a push-restriction actor on `master` in
`commons-settings.yml`. That entry never applied. GitHub limits
`restrictions.users`, `.teams` and `.apps` to organisation-owned
repositories, and the Probot Settings App passes the field through
unchanged. GitHub therefore rejected the whole `master` update with 422
on every consumer, because a personal account owns each of them.

The commons now declare no branch entry at all, neither `master`
([ADR-006](../decisions/adr-006-consumer-owned-master-protection.md))
nor `develop`
([ADR-005](../decisions/adr-005-consumer-owned-develop-protection.md)).
Each consumer declares its own complete entries. That protection,
together with any rulesets, decides whether the App may push to a
branch. Nothing restricts pushes to `master` unless the consumer
declares it.

This repository declares `master` in its own `.github/settings.yml`:

```yaml title=".github/settings.yml"
branches:
  - name: master
    protection:
      required_pull_request_reviews: null
      required_status_checks: null
      enforce_admins: true
      restrictions: null
```

On `master` this applies the protection to admins as well and requires
no checks, no reviews and no push restriction. Force pushes and deletions stay
blocked, because the API defaults both to `false`. These are the values
that were live before the entry existed.

!!! warning "Push restrictions need an organisation"
    GitHub accepts `restrictions` with users, teams or apps only on
    organisation-owned repositories. In a personal-account repository,
    declare `restrictions: null`. Anything else fails the whole update
    for the branch with 422, and the entry applies nothing. An
    organisation-owned consumer that wants only the App to push to a
    branch declares the slug **`nolte-portfolio-app`** under
    `restrictions.apps` in its own entry.

!!! tip "Install the App before you restrict a branch to it"
    Before a consumer restricts pushes on a branch to the App, the App
    must already live in that repository. An App that hasn't reached
    the repository can't push. The only effect of an early restriction
    is to block direct pushes from any other actor.

---

## Version-bearing file alignment (primary path)

Phase 2 installs the App. `develop`'s own branch protection and
rulesets must also let the App push there. After that, a caller can
opt into the **workflow-driven primary path** for version-bearing-file
alignment (`spec/project/release-automation/` §Version-bearing file
alignment).
The caller passes `auto-align: true` to `reusable-release-publish.yml`.
With the opt-in set and an App token present, the reusable then does
three things before it verifies:

1. it updates every version-bearing file to the target tag under its
   transform. It keeps each file's existing `v`-prefix convention and
   bumps **every** match of an array selector such as
   `$.plugins[].version` in a multi-plugin `marketplace.json`.
2. it commits the aggregate change as `chore(release): <tag>` on
   `develop` under the App's identity.
3. it pushes the commit through the declared bypass and realigns the
   draft's `target_commitish` to it. The published tag then comes from
   exactly the aligned tree.

The align step needs **both the opt-in and the App token**. It runs
only when `auto-align: true` meets a token from the mint step.
Otherwise the workflow skips the step and falls back to the **operator
path**. There, a human opens a `chore(release): <tag>` PR, squash-
merges it through the UI, then dispatches `release-publish`. Both paths
land the identical `chore(release): <tag>` commit shape. Only the
credential that creates it differs. A `dry_run` dispatch aligns and
verifies on the runner. It never pushes and never realigns the draft.

!!! warning "First real run validates the protected push"
    A direct push to `develop` under `enforce_admins: true` with
    required status checks works only when the App is a genuine bypass
    actor. `dry_run` can't exercise it. The remediation for a rejected
    first push lies in `develop`'s branch protection or rulesets, which
    the consumer owns
    ([ADR-005](../decisions/adr-005-consumer-owned-develop-protection.md)).
    It's not a workflow change.
    The run degrades to the operator fallback rather than wedging the
    release.

---

## Related work

- Tracking issue: [#330](https://github.com/nolte/gh-plumbing/issues/330)
- PR introducing the wrapper pattern in `nolte/gh-plumbing`
- Earlier escape hatch for the `release-publish` cascade gap:
  [#329](https://github.com/nolte/gh-plumbing/pull/329)
- Spec sections: `spec/project/workflow-health/` §Known platform
  constraints, `spec/project/release-automation/` §Permissions and
  protection
