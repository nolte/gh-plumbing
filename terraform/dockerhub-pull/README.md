# Docker-hub-pull terraform module

Provisions the Docker Hub **read** credential that this repository's reusable
workflows already know how to consume: an Actions variable `DOCKERHUB_USERNAME`
and an Actions secret `DOCKERHUB_TOKEN` on every repository that pulls images
during CI.

## Why a credential at all

An anonymous Docker Hub pull is rate-limited **per source IP**. On
GitHub-hosted runners that IP is shared with every other tenant of the runner
pool, so the budget can be exhausted by strangers and a pull failure lands on
whichever pull request is unlucky — a red required check with no relation to
its diff.

Authenticating changes the unit the limit is counted in: the quota becomes
**per account**, consumed only by the account's own pulls, and the ceiling is
higher. The measured headers of a rate-limited public image
(`ratelimit-limit: 100;w=3600`, `pull_limit_interval: 21600`) are worth
re-checking before quoting a number — Docker has changed the published limits
more than once, and the registry reports the live values on every pull.

The nominal factor is the smaller half of the benefit. Not sharing the counter
with the rest of the internet is the larger half.

## What it provisions

### Organisation mode

- one org-level Actions variable `DOCKERHUB_USERNAME`, `visibility = selected`
- one org-level Actions secret `DOCKERHUB_TOKEN`, `visibility = selected`

Both scoped to `var.consumer_repositories`.

### User mode

- one repository-level Actions variable `DOCKERHUB_USERNAME` per consumer
- one repository-level Actions secret `DOCKERHUB_TOKEN` per consumer

Personal accounts have no org-level Actions storage, so the module creates the
pair on each repository instead.

### Why the username is a variable and the token is a secret

The username is not confidential — it is part of every image reference the
account publishes. More decisively, the consuming workflows gate their login
step on it:

```yaml
if: ${{ inputs.dockerhub-username != '' }}
```

A job-level `if:` cannot read the `secrets` context reliably, so the gate needs
a variable. This is the same split, for the same reason, as `PORTFOLIO_APP_ID`
versus `PORTFOLIO_APP_PRIVATE_KEY` in the `portfolio-app` module next door.

## What it doesn't provision

- **The Docker Hub account and the token itself.** Both are created by hand at
  <https://app.docker.com/settings/personal-access-tokens>; there is no Docker
  Hub Terraform provider in this portfolio's stack. The module distributes a
  token that already exists.
- **A login step in any workflow.** `reusable-pre-commit.yaml` already carries
  one. A workflow that pulls from Docker Hub outside that lane — a
  `build-push-action` reading a public base image, a compose stack in an E2E
  job — needs its own `docker/login-action` step wired to the same pair.
- **Any push capability.** Nothing this module serves writes to a registry, so
  the token it distributes should not be able to.

## Pre-conditions

1. A Docker Hub personal access token exists, scoped **Public Repo Read-only**.
   Nothing downstream pushes; a broader scope only widens what a leaked token
   reaches.
2. The provider token (`GITHUB_TOKEN`) can write Actions variables and secrets
   on every repository in `var.consumer_repositories` — `repo` scope for a
   personal account.
3. Every repository in that list exists. The data lookup fails the plan
   otherwise, which is deliberate: a typo should not silently provision nothing.
4. The `integrations/github` provider resolves to **6.12.0 or newer**. The
   module writes the secret through `value`, which that release introduced
   while deprecating `plaintext_value` and `encrypted_value` — measured
   against the provider schema, not inferred. A root pinned below 6.12 fails
   `terraform validate` with *"An argument named `value` is not expected
   here"* rather than misbehaving quietly. The sibling `portfolio-app` module
   still declares `~> 6.6` and still writes `plaintext_value`; it therefore
   emits deprecation warnings under a current provider, which is a separate
   fix.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `organization` | `string` | `""` | Owning organisation. Mutually exclusive with `user`. |
| `user` | `string` | `""` | Owning user account. Mutually exclusive with `organization`. |
| `dockerhub_username` | `string` | — | Docker Hub account name. Lowercase; an e-mail address is rejected. |
| `dockerhub_token` | `string` (sensitive) | — | Docker Hub PAT, `Public Repo Read-only`. |
| `consumer_repositories` | `list(string)` | — | Repositories that receive the pair. At least one. |

## Outputs

| Name | Description |
|---|---|
| `mode` | `organization` or `user`, mirroring which input was set. |
| `owner` | The resolved owner string. |
| `configured_repositories` | Repositories that now carry the pair. |
| `variable_name` | `DOCKERHUB_USERNAME`. |
| `secret_name` | `DOCKERHUB_TOKEN`. |

## Usage

```hcl
module "dockerhub_pull" {
  source = "github.com/nolte/gh-plumbing//terraform/dockerhub-pull?ref=develop"

  user               = "octocat"
  dockerhub_username = var.dockerhub_username
  dockerhub_token    = var.dockerhub_token

  consumer_repositories = [
    "a-repo-whose-ci-pulls-images",
    "another-one",
  ]
}
```

The consuming workflow needs no change if it already calls
`reusable-pre-commit.yaml` the documented way:

```yaml
jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
    with:
      dockerhub-username: ${{ vars.DOCKERHUB_USERNAME }}
    secrets:
      dockerhub-token: ${{ secrets.DOCKERHUB_TOKEN }}
```

## The credential lives in Terraform state

`github_actions_secret` takes `plaintext_value`, and Terraform writes that
value into state. With a local, git-ignored state file that is acceptable for a
read-only token; it is **not** acceptable to move such a state to an
unencrypted remote backend. Treat the secret store the token came from as the
source of truth, and the state as a cache that happens to be readable.

## Rotation

1. Revoke the old token in Docker Hub.
2. Create a replacement with the same scope and put it in the secret store.
3. Re-run `apply`. The variable does not change; only the secret is replaced.

There is no window in which CI breaks: an invalid token makes the login step
fail, and every consuming workflow treats a failed login as "pull anonymously"
rather than as an error.

## Fail-open, by contract

Every consumer of this module degrades rather than breaks when the credential
is absent, wrong, or withheld:

- a repository not listed in `consumer_repositories` has no variable, so the
  login step is skipped
- a pull request from a **fork** receives no secrets at all; the login step
  runs with an empty password, fails, and is `continue-on-error`
- a revoked or mistyped token fails the same way

In all three cases the lane continues with anonymous pulls and emits a warning
naming the mode it ran in. A module that made CI depend on a registry
credential would trade a rate limit for an outage.

## Versioning

Pin by tag. `?ref=develop` tracks the default branch and will move under you.

## Related

- `terraform/portfolio-app/` — the sibling module this one mirrors
- `.github/workflows/reusable-pre-commit.yaml` — the first consumer
