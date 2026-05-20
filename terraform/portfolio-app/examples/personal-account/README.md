# Personal-account example: Portfolio-app module

End-to-end runnable example for a personal GitHub account (no
organisation). The module creates per-repository Actions variables and
secrets instead of organisation-scoped ones.

## Pre-conditions

- The portfolio GitHub App lives in every repository listed under
  `consumer_repositories` (manual install per repository from the
  App's settings page).
- The `GITHUB_TOKEN` environment variable holds a Personal Access
  Token with `repo` scope for the account. `admin:org` isn't needed
  because there is no organisation.
- `TF_VAR_portfolio_app_id` and `TF_VAR_portfolio_app_private_key`
  carry values from your local secret manager (not committed).

## Run

```sh
export GITHUB_TOKEN=ghp_...
export TF_VAR_portfolio_app_id=1234567
export TF_VAR_portfolio_app_private_key="$(cat ~/secrets/portfolio-app.pem)"

terraform init
terraform plan -out plan.tfplan
terraform apply plan.tfplan
```

## Expected result

- Repository-level Actions variable `PORTFOLIO_APP_ID` on every
  repository listed under `consumer_repositories`.
- Repository-level Actions secret `PORTFOLIO_APP_PRIVATE_KEY` on the
  same repositories.
- `mode` output reports `user`.
- No branch-protection change (`enable_branch_bypass = false`).

## Phase 2 follow-up

Once every repository in `consumer_repositories` runs the updated
wrapper pattern, flip `enable_branch_bypass` to `true` and re-apply.
Terraform plan output then shows added `github_branch_protection.bypass`
resources only.

## When to prefer organisation mode

If you maintain three or more consumer repositories and have an
organisation (or can create one), organisation mode is cheaper to
run. One organisation variable and one organisation secret with
`visibility = "selected"` cover every consumer at once.
Per-repository mode creates `2 × N` resources for `N` consumers.
