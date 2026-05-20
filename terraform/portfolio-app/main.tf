# Owner resolution — exactly one of var.organization or var.user must
# be set. Locals derive the canonical owner string used downstream for
# repository lookups and a `is_org` flag that switches resource shape.
locals {
  is_org        = var.organization != ""
  is_user       = var.user != ""
  owner         = local.is_org ? var.organization : var.user
  user_repo_set = local.is_user ? toset(var.consumer_repositories) : toset([])
}

# Hard-fail at plan time when both or neither owner inputs are set. A
# null_resource with a precondition keeps the error message close to
# the actual misconfiguration and avoids confusing Terraform with two
# branches that both look valid.
resource "terraform_data" "owner_check" {
  lifecycle {
    precondition {
      condition     = (var.organization != "") != (var.user != "")
      error_message = "Set exactly one of `organization` or `user`. The current configuration sets ${var.organization != "" ? "organization" : "neither"}${var.user != "" ? " and user" : ""}."
    }
  }
}

# Data lookup for each consumer repository — needed to translate names
# into the numeric repo IDs the variable / secret / branch-protection
# resources require.
data "github_repository" "consumers" {
  for_each  = toset(var.consumer_repositories)
  full_name = "${local.owner}/${each.value}"
}

# --- Organisation mode ------------------------------------------------
#
# One org-level Actions variable + secret with visibility=selected
# scoped to the consumer-repositories list. New consumers join by
# extending consumer_repositories; the variable + secret cover them
# automatically.

# Org-level Actions variable holding the App ID.
#
# The wrapper workflows in nolte/gh-plumbing read vars.PORTFOLIO_APP_ID
# inside their `if:` condition. Storing the ID as a variable (not a
# secret) is intentional — the ID is non-sensitive and the GitHub Actions
# `secrets` context cannot be read reliably from job-level `if:` blocks.
resource "github_actions_organization_variable" "portfolio_app_id" {
  count = local.is_org ? 1 : 0

  variable_name = "PORTFOLIO_APP_ID"
  visibility    = "selected"
  value         = var.app_id
  selected_repository_ids = [
    for r in data.github_repository.consumers : r.repo_id
  ]
}

# Org-level Actions secret holding the App's PEM private key.
#
# Combined with PORTFOLIO_APP_ID above, this lets each consumer's
# wrapper mint a short-lived App installation token via
# actions/create-github-app-token@v2.
resource "github_actions_organization_secret" "portfolio_app_private_key" {
  count = local.is_org ? 1 : 0

  secret_name     = "PORTFOLIO_APP_PRIVATE_KEY"
  visibility      = "selected"
  plaintext_value = var.app_private_key
  selected_repository_ids = [
    for r in data.github_repository.consumers : r.repo_id
  ]
}

# --- User mode --------------------------------------------------------
#
# Personal GitHub accounts have no org-level Actions variables or
# secrets, so the module falls back to per-repository resources. New
# consumers require explicit extension of consumer_repositories (same
# as org mode), and Terraform creates the variable + secret on each
# new repo on the next apply.

resource "github_actions_variable" "portfolio_app_id" {
  for_each = local.user_repo_set

  repository    = each.value
  variable_name = "PORTFOLIO_APP_ID"
  value         = var.app_id
}

resource "github_actions_secret" "portfolio_app_private_key" {
  for_each = local.user_repo_set

  repository      = each.value
  secret_name     = "PORTFOLIO_APP_PRIVATE_KEY"
  plaintext_value = var.app_private_key
}

# --- Phase 2 (opt-in): branch-protection bypass -----------------------
#
# Declares the App as a push-restriction (bypass) actor on each
# protected branch of each consumer repository. Identical shape in
# organisation and user mode — the resource keys off repo node IDs,
# which the data lookup above already provides for both modes.
#
# Caveat: this only works for branches that have a protection rule. The
# resource will create one if missing; consumers that manage branch
# protection through Probot Settings App + .github/settings.yml should
# review whether Terraform should own the rule or just augment it (the
# integrations/github provider does not patch existing rules — it
# replaces them on the keys it manages).
resource "github_branch_protection" "bypass" {
  for_each = var.enable_branch_bypass ? {
    for pair in setproduct(var.consumer_repositories, var.protected_branches) :
    "${pair[0]}::${pair[1]}" => {
      repository = pair[0]
      branch     = pair[1]
    }
  } : {}

  repository_id  = data.github_repository.consumers[each.value.repository].node_id
  pattern        = each.value.branch
  enforce_admins = true

  restrict_pushes {
    push_allowances = ["/${var.app_slug}"]
  }
}
