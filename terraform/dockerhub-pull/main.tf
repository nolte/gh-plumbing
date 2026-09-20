# Owner resolution — exactly one of var.organization or var.user must be
# set. Locals derive the canonical owner string used for repository
# lookups and an `is_org` flag that switches resource shape. Identical to
# the portfolio-app module in this repository, deliberately: two shared
# modules that provision per-repository Actions credentials should not
# disagree about how an owner is named.
locals {
  is_org        = var.organization != ""
  is_user       = var.user != ""
  owner         = local.is_org ? var.organization : var.user
  user_repo_set = local.is_user ? toset(var.consumer_repositories) : toset([])
}

# Hard-fail at plan time when both or neither owner inputs are set, so the
# error names the misconfiguration instead of surfacing later as an empty
# resource set that looks like a successful no-op.
resource "terraform_data" "owner_check" {
  lifecycle {
    precondition {
      condition     = (var.organization != "") != (var.user != "")
      error_message = "Set exactly one of `organization` or `user`. The current configuration sets ${var.organization != "" ? "organization" : "neither"}${var.user != "" ? " and user" : ""}."
    }
  }
}

# Data lookup for each consumer repository. Org mode needs the numeric
# repo IDs for `selected_repository_ids`; user mode addresses repositories
# by name, but the lookup runs in both modes so a typo in
# consumer_repositories fails at plan time rather than creating a variable
# on a repository nobody meant.
data "github_repository" "consumers" {
  for_each  = toset(var.consumer_repositories)
  full_name = "${local.owner}/${each.value}"
}

# --- Organisation mode ------------------------------------------------

# Org-level Actions variable holding the Docker Hub account name.
#
# A VARIABLE and not a secret, for two independent reasons. It is not
# confidential — the account name is part of every image reference the
# account publishes. And the consuming workflows gate the login step on
# it (`if: inputs.dockerhub-username != ''`), which a secret could not
# serve: the `secrets` context is not readable from a job-level `if:`.
# Same reasoning as PORTFOLIO_APP_ID in the portfolio-app module.
resource "github_actions_organization_variable" "dockerhub_username" {
  count = local.is_org ? 1 : 0

  variable_name = "DOCKERHUB_USERNAME"
  visibility    = "selected"
  value         = var.dockerhub_username
  selected_repository_ids = [
    for r in data.github_repository.consumers : r.repo_id
  ]
}

# Org-level Actions secret holding the Docker Hub personal access token.
#
# `value`, not `plaintext_value`. Measured against the provider schema rather
# than copied from the sibling module: `value` first appears in
# integrations/github 6.12.0, and the same release marks both
# `plaintext_value` and `encrypted_value` deprecated. That is why this module
# requires `~> 6.12` where portfolio-app still asks for `~> 6.6` — a new module
# should not be born writing a deprecated argument, and supporting 6.6-6.11 would
# force exactly that.
resource "github_actions_organization_secret" "dockerhub_token" {
  count = local.is_org ? 1 : 0

  secret_name = "DOCKERHUB_TOKEN"
  visibility  = "selected"
  value       = var.dockerhub_token
  selected_repository_ids = [
    for r in data.github_repository.consumers : r.repo_id
  ]
}

# --- User mode --------------------------------------------------------
#
# Personal GitHub accounts have no org-level Actions variables or
# secrets, so the module falls back to per-repository resources. A new
# consumer requires an explicit extension of consumer_repositories; until
# then its workflows pull anonymously, which is the documented degraded
# mode rather than a failure.

resource "github_actions_variable" "dockerhub_username" {
  for_each = local.user_repo_set

  repository    = each.value
  variable_name = "DOCKERHUB_USERNAME"
  value         = var.dockerhub_username
}

# `value` for the reason given on the organisation-mode secret above.
resource "github_actions_secret" "dockerhub_token" {
  for_each = local.user_repo_set

  repository  = each.value
  secret_name = "DOCKERHUB_TOKEN"
  value       = var.dockerhub_token
}
