# Plan-time checks of the owner-mode preconditions in
# terraform_data.owner_check. The mocked provider needs no GitHub
# credentials and makes no API calls.
#
# `terraform test` with `mock_provider` needs Terraform >= 1.7. That
# applies to running these tests only; the module itself keeps its
# >= 1.6 floor in versions.tf.
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
