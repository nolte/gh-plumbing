# Basic example: Portfolio-app module

End-to-end runnable example for a single consumer repository
(`nolte/gh-plumbing` dog-fooding itself).

## Pre-conditions

- The portfolio GitHub App lives in `nolte/gh-plumbing`.
- The `GITHUB_TOKEN` environment variable holds a token with
  `admin:org`, `repo`, and `read:org` scopes for the `nolte`
  organisation.
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

- Organisation-level Actions variable `PORTFOLIO_APP_ID` visible to
  `nolte/gh-plumbing`.
- Organisation-level Actions secret `PORTFOLIO_APP_PRIVATE_KEY`
  visible to `nolte/gh-plumbing`.
- No branch-protection change (`enable_branch_bypass = false`).

## Phase 2 follow-up

Once every repository in `consumer_repositories` runs the updated
wrapper pattern, flip `enable_branch_bypass` to `true` and re-apply.
Terraform plan output then shows added `github_branch_protection.bypass`
resources only.
