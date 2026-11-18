# Plan-time checks of the owner-mode preconditions in
# terraform_data.owner_check. The mocked provider needs no GitHub
# credentials and makes no API calls.
#
# Because of `mock_provider`, init, validate and test in this directory
# need Terraform >= 1.7. The >= 1.6 floor in versions.tf holds when the
# module is consumed through `source`.
#
# Run from terraform/portfolio-app:
#   terraform init -backend=false
#   terraform test

mock_provider "github" {}

variables {
  app_id          = "1234567"
  app_slug        = "example-portfolio-bot"
  app_private_key = "-----BEGIN RSA PRIVATE KEY-----\nnot-a-real-key\n-----END RSA PRIVATE KEY-----\n"

  consumer_repositories = ["example-repo"]
}

run "user_mode_refuses_branch_bypass" {
  command = plan

  variables {
    user                 = "octocat"
    enable_branch_bypass = true
  }

  expect_failures = [
    terraform_data.owner_check,
  ]
}

run "organization_mode_allows_branch_bypass" {
  command = plan

  variables {
    organization         = "example-org"
    enable_branch_bypass = true
  }

  assert {
    condition     = output.mode == "organization"
    error_message = "Expected organisation mode."
  }

  assert {
    condition     = length(github_branch_protection.bypass) == 2
    error_message = "Expected one bypass entry per default protected branch."
  }
}

# Both owners set: the plan fails on terraform_data.owner_check.
# `expect_failures` can't tell which of its preconditions fired, so this
# run doesn't show that the bypass message stays silent here. That was
# checked by hand, by running this case without `expect_failures`: the
# output showed only "Set exactly one of `organization` or `user`".
run "both_owners_with_branch_bypass" {
  command = plan

  variables {
    organization         = "example-org"
    user                 = "octocat"
    enable_branch_bypass = true
  }

  expect_failures = [
    terraform_data.owner_check,
  ]
}

run "user_mode_without_branch_bypass" {
  command = plan

  variables {
    user                 = "octocat"
    enable_branch_bypass = false
  }

  assert {
    condition     = output.mode == "user"
    error_message = "Expected user mode."
  }

  assert {
    condition     = length(github_branch_protection.bypass) == 0
    error_message = "Expected no bypass entries in user mode."
  }
}
