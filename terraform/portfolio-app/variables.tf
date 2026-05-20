variable "organization" {
  description = "GitHub organisation (or user) that owns the consumer repositories. The provider must be authenticated against this scope."
  type        = string
}

variable "app_id" {
  description = "Numeric ID of the portfolio GitHub App (visible on its settings page). Written to the org-level Actions variable PORTFOLIO_APP_ID."
  type        = string

  validation {
    condition     = can(regex("^[0-9]+$", var.app_id))
    error_message = "app_id must be the numeric App ID (digits only)."
  }
}

variable "app_private_key" {
  description = "PEM-encoded private key for the portfolio GitHub App. Written to the org-level Actions secret PORTFOLIO_APP_PRIVATE_KEY. Marked sensitive."
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
  description = "Names of repositories in var.organization that should consume the portfolio App. The module sets visibility=selected on the org-level variable + secret to this list, and (when enable_branch_bypass is true) configures branch protection with the App as a bypass actor."
  type        = list(string)

  validation {
    condition     = length(var.consumer_repositories) > 0
    error_message = "consumer_repositories must list at least one repository name."
  }
}

variable "enable_branch_bypass" {
  description = "When true, configure branch protection on var.protected_branches for every consumer repository with var.app_slug declared as a push-restriction (bypass) actor. This is Phase 2 of issue #330. Default off so Phase 0 (credentials + selection) can land independently."
  type        = bool
  default     = false
}

variable "protected_branches" {
  description = "Branches per consumer repository that receive the bypass entry when enable_branch_bypass is true. Order does not matter."
  type        = list(string)
  default     = ["develop", "master"]
}
