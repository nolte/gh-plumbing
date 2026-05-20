# Org-level Actions variable holding the App ID.
#
# The wrapper workflows in nolte/gh-plumbing read vars.PORTFOLIO_APP_ID
# inside their `if:` condition. Storing the ID as a variable (not a
# secret) is intentional — the ID is non-sensitive and the GitHub Actions
# `secrets` context cannot be read reliably from job-level `if:` blocks.
resource "github_actions_organization_variable" "portfolio_app_id" {
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
  secret_name     = "PORTFOLIO_APP_PRIVATE_KEY"
  visibility      = "selected"
  plaintext_value = var.app_private_key
  selected_repository_ids = [
    for r in data.github_repository.consumers : r.repo_id
  ]
}

# Data lookup for each consumer repository — needed to translate names
# into the numeric repo IDs both organisation-secret/-variable
# resources require.
data "github_repository" "consumers" {
  for_each  = toset(var.consumer_repositories)
  full_name = "${var.organization}/${each.value}"
}

# Phase 2 (opt-in): declare the App as a push-restriction (bypass)
# actor on each protected branch of each consumer repository. This
# enables the workflow-driven primary path of
# spec/project/release-automation/ §Version-bearing file alignment.
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
