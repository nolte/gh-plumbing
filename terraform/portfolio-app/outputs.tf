output "configured_repositories" {
  description = "Repository names that now see the portfolio App's variable and secret. Match against var.consumer_repositories to confirm."
  value       = [for r in data.github_repository.consumers : r.name]
}

output "variable_name" {
  description = "Name of the org-level Actions variable consumers reference (PORTFOLIO_APP_ID). Exposed for symmetry with the wrapper docs."
  value       = github_actions_organization_variable.portfolio_app_id.variable_name
}

output "secret_name" {
  description = "Name of the org-level Actions secret consumers reference (PORTFOLIO_APP_PRIVATE_KEY). Exposed for symmetry with the wrapper docs."
  value       = github_actions_organization_secret.portfolio_app_private_key.secret_name
}

output "branch_bypass_enabled" {
  description = "True when var.enable_branch_bypass was set; informational, mirrors the input."
  value       = var.enable_branch_bypass
}

output "branch_bypass_pairs" {
  description = "Repository::branch pairs that received the App as a push-restriction actor. Empty when enable_branch_bypass is false."
  value       = keys(github_branch_protection.bypass)
}
