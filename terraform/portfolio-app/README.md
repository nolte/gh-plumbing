# Portfolio-app terraform module

Provisions the **Actions variable and secret** and, in organisation
mode, (optionally) the **branch-protection bypass** that the
[portfolio GitHub App](../../docs/en/portfolio-app/setup.md) needs to
close the `GITHUB_TOKEN` cascade gap tracked in
[issue #330](https://github.com/nolte/gh-plumbing/issues/330).

The module is the Terraform-driven alternative to the manual
GitHub-UI checklist in `docs/en/portfolio-app/setup.md`. It replaces
three manual steps (set organisation variable, set organisation
secret, repeat per repository) with one `terraform apply`.

## Owner modes

The module runs in one of two modes depending on which owner input
you set. Pick the one that matches the GitHub account that owns the
consumer repositories.

| Mode | Set | Resources |
|---|---|---|
| Organisation mode | `organization = "<org>"` | one organisation-level variable and secret with `visibility = "selected"` scoped to `consumer_repositories` |
| User mode | `user = "<handle>"` | one repository-level variable and secret per repository in `consumer_repositories` (organisation-level Actions resources don't exist for personal accounts) |

Set **exactly one** input. The module fails fast at plan time when
the configuration sets both or neither.

## What it provisions

### Organisation mode

| Resource | Scope | Purpose |
|---|---|---|
| `github_actions_organization_variable.portfolio_app_id` | organisation-wide, `visibility = "selected"` | Holds the App ID under the name `PORTFOLIO_APP_ID`. Wrappers read it from `vars.PORTFOLIO_APP_ID`. |
| `github_actions_organization_secret.portfolio_app_private_key` | organisation-wide, `visibility = "selected"` | Holds the private key under the name `PORTFOLIO_APP_PRIVATE_KEY`. Wrappers read it from `secrets.PORTFOLIO_APP_PRIVATE_KEY`. |
| `github_actions_organization_secret_repositories.portfolio_app_private_key` | the organisation secret's repository access | Grants the repositories in `consumer_repositories` access to `PORTFOLIO_APP_PRIVATE_KEY`. A separate resource because provider 6.12.0 deprecated `selected_repository_ids` on the secret. |

Updating the secret, for example after rotating `app_private_key`,
sends no repository list. This module hasn't confirmed that GitHub
keeps the existing selection in that case, and the access resource
plans no change in that apply. After the first organisation-mode
apply and after each key rotation, check the selection:

```sh
gh api orgs/<org>/actions/secrets/PORTFOLIO_APP_PRIVATE_KEY/repositories \
  --jq '.repositories[].full_name'
```

If a consumer repository is missing, a second `terraform apply`
restores the list.

### User mode

| Resource | Scope | Purpose |
|---|---|---|
| `github_actions_variable.portfolio_app_id` (per repository) | repository-level | Holds the App ID under the name `PORTFOLIO_APP_ID` on each consumer repository. |
| `github_actions_secret.portfolio_app_private_key` (per repository) | repository-level | Holds the private key under the name `PORTFOLIO_APP_PRIVATE_KEY` on each consumer repository. |

### Branch-protection bypass (organisation mode only)

| Resource | Scope | Purpose |
|---|---|---|
| `github_branch_protection.bypass` (optional) | per repository per branch | Declares the App as a push-restriction (bypass) actor on the protected branches. Enables the workflow-driven primary path of `spec/project/release-automation/` §Version-bearing file alignment. |

GitHub documents push restrictions for users, teams and apps as
available only on organisation-owned repositories. The module
therefore fails at plan time when the configuration sets `user`
together with `enable_branch_bypass = true`. In user mode, leave the flag off.

The bypass names the App by its node ID, set through `app_node_id`.
The module fails at plan time when `enable_branch_bypass = true` and
`app_node_id` is empty. See [Find the App node identifier](#find-the-app-node-identifier).

## What it doesn't provision

- **The GitHub App itself.** GitHub exposes no public API to *create*
  an App. The App ID and private key come from the registration flow
  at `https://github.com/settings/apps/new`. Register the App
  manually first, then feed the resulting App ID, private key, and
  (for the bypass) App node ID into this module.
- **The App's per-repository installation.** Installing an App into a
  repository is a UI or account-owner action that the Terraform
  GitHub provider doesn't expose consistently. The module assumes the
  App already lives in every repository listed in
  `consumer_repositories`. The Terraform module covers everything
  downstream of the App being live; it doesn't replace the one-time
  install click.

## Pre-conditions

Before `terraform apply`:

1. The portfolio App carries the permissions listed in
   `docs/en/portfolio-app/setup.md` §Permissions the app requires:
   `Contents: Read and write`, `Pull requests: Read and write`,
   `Issues: Read and write`, `Actions: Read-only`, plus the implicit
   `Metadata: Read-only` baseline. `Issues: Read and write` is what
   lets an App-driven squash-merge automatically close issues referenced
   via `Closes #N` in the PR body; without it the merge succeeds but the
   issue stays `OPEN`. The Terraform module doesn't manage App
   permissions; they're set on the App's registration page in the
   GitHub UI.
2. The App lives in every repository you intend to list under
   `consumer_repositories`.
3. The Terraform provider holds credentials for the owner account
   (`var.organization` or `var.user`) with sufficient permissions:
   - **Organisation mode:** `admin:org` (organisation-secret and
     organisation-variable management), `repo` (branch protection,
     only needed when `enable_branch_bypass = true`), `read:org`
     (data lookup over the organisation's repository list).
   - **User mode:** `repo` (repository-level Actions variables and
     secrets). No `admin:org` needed.
4. The App private key lives locally, typically loaded from an
   external secret manager and never committed.
5. The App ID and, for the bypass, the App node ID are at hand. Both
   are ordinary configuration values, not secrets.

## Inputs

| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| `organization` | string | one of | `""` | GitHub organisation that owns the consumer repositories. Mutually exclusive with `user`. |
| `user` | string | one of | `""` | GitHub user account that owns the consumer repositories. Mutually exclusive with `organization`. |
| `app_id` | string | yes | n/a | Numeric App ID. |
| `app_private_key` | string (sensitive) | yes | n/a | Private key in Privacy-Enhanced-Mail format. |
| `app_slug` | string | no | `""` | App slug (the path segment after `/apps/` in the App's web address). Optional. The module no longer reads it; the bypass uses `app_node_id`. Kept so existing module calls keep working. |
| `app_node_id` | string | when the bypass is on | `""` | Node ID of the App (starts with `A_` or `MDM6QXBw`). The push-restriction actor when `enable_branch_bypass = true`. See [Find the App node identifier](#find-the-app-node-identifier). |
| `consumer_repositories` | list(string) | yes | n/a | Repositories that should see the variable and secret (and, in organisation mode, the bypass entry when enabled). |
| `enable_branch_bypass` | `bool` | no | `false` | Phase 2 toggle, organisation mode only. With `user` and `true`, the module fails at plan time. Flip to `true` only after the App lives in every consumer repository and after a cross-repository security review. |
| `protected_branches` | list(string) | no | `["develop", "master"]` | Branches that receive the bypass entry when Phase 2 is on (organisation mode only). |

## Find the App node identifier

The bypass needs the App's node ID, not its slug. The provider reads
an entry that starts with `/` as a user login, and an App slug isn't
a user login.

If your token can see the App, ask the GitHub API:

```sh
gh api apps/<slug> --jq .node_id
```

If this call returns `404` (the token can't see a private App),
authenticate as the App with a JSON Web Token (JWT) signed by its
private key and call `GET /app`. The response carries the node ID in `.node_id`.

The value starts with `A_` or `MDM6QXBw`. The `<slug>[bot]` user has
its own node ID that starts with `BOT_`. That ID isn't the App node
ID, and the module rejects it.

## Outputs

| Name | Description |
|---|---|
| `mode` | Which owner mode the module ran in. Value is `organization` or `user`. |
| `owner` | The owner string (organisation or user) the module resolved at plan time. |
| `configured_repositories` | Repository names now seeing the variable and secret (organisation-scoped or repository-scoped, depending on mode). |
| `variable_name` | `PORTFOLIO_APP_ID` (informational, mirrors the wrapper contract). |
| `secret_name` | `PORTFOLIO_APP_PRIVATE_KEY` (informational, mirrors the wrapper contract). |
| `branch_bypass_enabled` | Mirrors the input flag. |
| `branch_bypass_pairs` | `repo::branch` pairs that received the bypass entry. Empty when Phase 2 is off, and always empty in user mode. |

## Usage

Two runnable examples ship with the module:

- [`examples/basic/`](./examples/basic/) shows organisation mode
  (`organization = "nolte"`).
- [`examples/personal-account/`](./examples/personal-account/) shows
  user mode (`user = "octocat"`).

The shortest possible adoption in organisation mode:

```hcl
module "portfolio_app" {
  source = "github.com/nolte/gh-plumbing//terraform/portfolio-app?ref=develop"

  organization = "nolte"
  app_id       = var.portfolio_app_id

  # Loaded from your secret manager (environment variable, vault, sops, …).
  app_private_key = var.portfolio_app_private_key

  consumer_repositories = [
    "gh-plumbing",
    "claude-shared",
    # add further consumers as they adopt the wrapper pattern
  ]

  # Default off. Flip once the App lives in every listed repository
  # and the consumer wrappers carry the new pattern. The bypass then
  # needs the App node ID (see "Find the App node identifier").
  enable_branch_bypass = false
  # app_node_id        = "A_kwDO..."
}
```

The shortest possible adoption in user mode (same module call, swap
`organization` for `user`):

```hcl
module "portfolio_app" {
  source = "github.com/nolte/gh-plumbing//terraform/portfolio-app?ref=develop"

  user            = "octocat"
  app_id          = var.portfolio_app_id
  app_private_key = var.portfolio_app_private_key

  consumer_repositories = [
    "my-repo-with-gh-plumbing-wrappers",
  ]

  enable_branch_bypass = false
}
```

## When to pick which mode

| Signal | Mode |
|---|---|
| You administer a GitHub organisation | organisation |
| You have three or more consumer repositories | organisation (one variable + one secret cover all) |
| You have a personal GitHub account only | user |
| You only have one or two consumer repositories | either; user mode has lower setup overhead per consumer |

## Phase roll-out

The module supports the three-phase migration described in
`docs/en/portfolio-app/setup.md`:

| Phase | Module input | Result |
|---|---|---|
| Phase 0 | `enable_branch_bypass = false`, partial `consumer_repositories` | Organisation variable and secret created, visible only to the listed repositories (user mode: one repository-level pair per listed repository). Wrappers in those repositories can adopt the App-token path. |
| Phase 2 (organisation mode only) | `enable_branch_bypass = true`, same `consumer_repositories` | Branch protection updated with the App as a push-restriction actor. Workflow-driven primary path of `release-automation` becomes available. User mode stays at Phase 0 settings; the module refuses this input there. |
| Phase 3 | extend `consumer_repositories` as new repositories adopt the wrappers | Variable and secret automatically extend to the new repositories. |

## Tests

`tests/owner_mode.tftest.hcl` checks the owner-mode preconditions at
plan time with a mocked provider, without GitHub credentials. Run
`terraform init -backend=false` and then `terraform test` in this
directory. Because of the test file's `mock_provider`, working inside
this directory (`init`, `validate`, `test`) needs Terraform 1.7 or
later. The 1.6 floor in `versions.tf` holds when you consume the
directory as a module through `source`.

## Versioning

The module follows the gh-plumbing release cadence. Pin it like any
other reusable artefact:

```hcl
source = "github.com/nolte/gh-plumbing//terraform/portfolio-app?ref=v1.x.y"
```

Use `?ref=develop` only for portfolio repositories that intentionally
track the latest plumbing changes.

## Related

- Issue: [#330](https://github.com/nolte/gh-plumbing/issues/330)
- PR introducing the wrapper pattern in `nolte/gh-plumbing`
- Documentation: [`docs/en/portfolio-app/setup.md`](../../docs/en/portfolio-app/setup.md) and
  [`docs/de/portfolio-app/setup.md`](../../docs/de/portfolio-app/setup.md)
