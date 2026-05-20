variable "organization" {
  description = "GitHub organisation that owns the consumer repositories. Mutually exclusive with var.user — set exactly one. Org mode provisions one org-level variable + secret with visibility=selected; user mode provisions repo-level variables + secrets per consumer repository."
  type        = string
  default     = ""
}

variable "user" {
  description = "GitHub user account that owns the consumer repositories. Mutually exclusive with var.organization — set exactly one. Used when no GitHub organisation exists; the module then creates per-repository Actions variables and secrets instead of organisation-scoped ones."
  type        = string
  default     = ""
}

variable "app_id" {
  description = "Numeric ID of the portfolio GitHub App (visible on its settings page). Written to the Actions variable PORTFOLIO_APP_ID — org-scoped in organisation mode, repo-scoped in user mode."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.app_id))
    error_message = "app_id must be the numeric App ID (digits only)."
  }
}

variable "app_private_key" {
  description = "PEM-encoded private key for the portfolio GitHub App. Written to the Actions secret PORTFOLIO_APP_PRIVATE_KEY — org-scoped in organisation mode, repo-scoped in user mode. Marked sensitive."
  type        = string
  sensitive   = true

  validation {
    condition     = can(regex("BEGIN (RSA )?PRIVATE KEY", var.app_private_key))
    error_message = "app_private_key must contain a PEM header (e.g. -----BEGIN RSA PRIVATE KEY-----)."
  }
}

variable "app_slug" {
  description = "Slug of the portfolio GitHub App (the part of the App URL after /apps/, e.g. 'nolte-portfolio-bot'). Used to declare the App as a branch-protection bypass actor when enable_branch_bypass is true."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.app_slug))
    error_message = "app_slug must be lowercase letters, digits, and hyphens only."
  }
}

variable "consumer_repositories" {
  description = "Names of repositories under the owner (organisation or user) that should consume the portfolio App. Org mode sets visibility=selected on the org-level variable + secret to this list; user mode creates one variable + secret per repository here. When enable_branch_bypass is true, every listed repo also gets the App declared as a push-restriction actor."
  type        = list(string)

  validation {
    condition     = length(var.consumer_repositories) > 0
    error_message = "consumer_repositories must list at least one repository name."
  }
}

variable "enable_branch_bypass" {
  description = "When true, configure branch protection on var.protected_branches for every consumer repository with var.app_slug declared as a push-restriction (bypass) actor. This is Phase 2 of issue #330. Default off so Phase 0 (credentials + selection) can land independently. Works identically in organisation and user mode."
  type        = bool
  default     = false
}

variable "protected_branches" {
  description = "Branches per consumer repository that receive the bypass entry when enable_branch_bypass is true. Order does not matter."
  type        = list(string)
  default     = ["develop", "master"]
}
