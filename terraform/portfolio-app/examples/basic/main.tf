terraform {
  required_version = ">= 1.6.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.6"
    }
  }
}

# Authenticate against the org you administer. The token needs
# admin:org, repo, and read:org per the module README.
provider "github" {
  owner = "nolte"
  # token = read from GITHUB_TOKEN env var by default
}

# Load the App private key from somewhere that is NOT version control.
# This example uses an environment variable; swap for sops/vault/etc.
variable "portfolio_app_id" {
  type = string
}

variable "portfolio_app_private_key" {
  type      = string
  sensitive = true
}

module "portfolio_app" {
  source = "../.."

  organization    = "nolte"
  app_id          = var.portfolio_app_id
  app_slug        = "nolte-portfolio-bot"
  app_private_key = var.portfolio_app_private_key

  consumer_repositories = [
    "gh-plumbing",
  ]

  # Phase 0: leave bypass off until every consumer in the list above
  # has the App installed AND its wrappers updated. Flip to true in a
  # follow-up apply once both are confirmed.
  enable_branch_bypass = false
}

output "configured" {
  value = module.portfolio_app.configured_repositories
}
