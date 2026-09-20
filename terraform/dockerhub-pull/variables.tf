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

variable "dockerhub_username" {
  description = "Docker Hub account name the pull credentials belong to. Written to the Actions VARIABLE DOCKERHUB_USERNAME, not to a secret: a username is not confidential (it appears in every image reference), and the consuming workflows gate on it in a job-level `if:`, where the `secrets` context is not reliably readable. Use the account name, never an e-mail address — Docker Hub rejects the latter for registry login."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9_-]*$", var.dockerhub_username))
    error_message = "dockerhub_username must be a Docker Hub account name: lowercase letters, digits, '_' or '-'. An e-mail address or a name with capitals will authenticate locally but fail against the registry."
  }
}

variable "dockerhub_token" {
  description = "Docker Hub personal access token matching var.dockerhub_username, written to the Actions secret DOCKERHUB_TOKEN. A token scoped 'Public Repo Read-only' is sufficient for every consumer of this module — nothing it provisions pushes an image. Do NOT pass the account password: a password cannot be scoped down, cannot be revoked individually, and unlocks the account's whole surface. Marked sensitive."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.dockerhub_token) >= 8 && !can(regex("[[:space:]]", var.dockerhub_token))
    error_message = "dockerhub_token must be a non-trivial token without whitespace. A value carrying a newline is the usual symptom of `$(cat token.txt)` or a shell heredoc — the registry login then fails with a confusing 401."
  }
}

variable "consumer_repositories" {
  description = "Names of repositories under the owner (organisation or user) whose workflows pull from Docker Hub. Org mode sets visibility=selected on the org-level variable + secret to this list; user mode creates one variable + secret per repository here. A repository absent from this list keeps pulling anonymously — which is a degraded mode, never a broken one."
  type        = list(string)

  validation {
    condition     = length(var.consumer_repositories) > 0
    error_message = "consumer_repositories must list at least one repository name."
  }
}
