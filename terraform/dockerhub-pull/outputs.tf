output "mode" {
  description = "Which owner mode the module ran in — `organization` or `user`. Mirrors which input was set."
  value       = local.is_org ? "organization" : "user"
}

output "owner" {
  description = "The owner string (organisation or user) the module resolved at plan time."
  value       = local.owner
}

output "configured_repositories" {
  description = "Repository names that now carry the Docker Hub variable and secret. Match against var.consumer_repositories to confirm; a repository missing here still pulls anonymously."
  value       = [for r in data.github_repository.consumers : r.name]
}

output "variable_name" {
  description = "Name of the Actions variable consumers reference (DOCKERHUB_USERNAME). Exposed so a wrapper's documentation can name it without hard-coding a second copy."
  value       = "DOCKERHUB_USERNAME"
}

output "secret_name" {
  description = "Name of the Actions secret consumers reference (DOCKERHUB_TOKEN). Exposed for symmetry with variable_name."
  value       = "DOCKERHUB_TOKEN"
}
