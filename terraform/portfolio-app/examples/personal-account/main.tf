terraform {
  required_version = ">= 1.6.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.12"
    }
  }
}

# Personal-account authentication. The token needs `repo` scope (to
# create repository-level Actions variables / secrets); no `admin:org`
# needed because there is no organisation.
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

  # Keep bypass off in user mode. GitHub documents push restrictions
  # for users, teams and apps as available only on organisation-owned
  # repositories, so the module fails at plan time when `user` is set
  # and this is true.
  enable_branch_bypass = false
}

output "mode" {
  value = module.portfolio_app.mode
}

output "configured" {
  value = module.portfolio_app.configured_repositories
}
