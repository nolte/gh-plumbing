terraform {
  required_version = ">= 1.6.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.6"
    }
  }
}

# Personal-account authentication. The token needs `repo` scope (to
# create repository-level Actions variables / secrets and to manage
# branch protection); no `admin:org` needed because there is no
# organisation.
provider "github" {
  owner = "octocat"
  # token = read from GITHUB_TOKEN env var by default
}

variable "portfolio_app_id" {
  type = string
}

variable "portfolio_app_private_key" {
  type      = string
  sensitive = true
}

module "portfolio_app" {
  source = "../.."

  # User mode — set `user` instead of `organization`.
  user            = "octocat"
  app_id          = var.portfolio_app_id
  app_slug        = "octocat-portfolio-bot"
  app_private_key = var.portfolio_app_private_key

  consumer_repositories = [
    "my-repo-with-gh-plumbing-wrappers",
  ]

  # Phase 0: leave bypass off until every consumer in the list above
  # has the App installed AND its wrappers updated. Flip to true in a
  # follow-up apply once both are confirmed.
  enable_branch_bypass = false
}

output "mode" {
  value = module.portfolio_app.mode
}

output "configured" {
  value = module.portfolio_app.configured_repositories
}
