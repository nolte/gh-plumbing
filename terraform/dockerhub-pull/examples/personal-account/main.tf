terraform {
  required_version = ">= 1.6.0"

  required_providers {
    github = {
      source  = "integrations/github"
      version = "~> 6.6"
    }
  }
}

# Personal-account authentication. The token needs `repo` scope to create
# repository-level Actions variables and secrets; no `admin:org`, because
# there is no organisation.
provider "github" {
  owner = "octocat"
  # token = read from GITHUB_TOKEN env var by default
}

variable "dockerhub_username" {
  type = string
}

variable "dockerhub_token" {
  type      = string
  sensitive = true
}

module "dockerhub_pull" {
  source = "../.."

  # User mode — set `user` instead of `organization`.
  user = "octocat"

  dockerhub_username = var.dockerhub_username
  dockerhub_token    = var.dockerhub_token

  consumer_repositories = [
    "a-repo-whose-ci-pulls-images",
    "another-one",
  ]
}

output "configured_repositories" {
  value = module.dockerhub_pull.configured_repositories
}
