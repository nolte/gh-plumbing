# Plan-time checks of the owner-mode and bypass preconditions in
# terraform_data.owner_check and github_branch_protection.bypass, and
# of the app_node_id input. The mocked provider needs no GitHub
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

# app_node_id is set so that only the user-mode precondition can fail.
run "user_mode_refuses_branch_bypass" {
  command = plan

  variables {
    user                 = "octocat"
    enable_branch_bypass = true
    app_node_id          = "A_kwDOexample"
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
    app_node_id          = "A_kwDOexample"
  }

  assert {
    condition     = output.mode == "organization"
    error_message = "Expected organisation mode."
  }

  assert {
    condition     = length(github_branch_protection.bypass) == 2
    error_message = "Expected one bypass entry per default protected branch."
  }

  assert {
    condition     = length(github_actions_organization_secret_repositories.portfolio_app_private_key) == 1
    error_message = "Expected the secret's repository access as a separate resource in organisation mode."
  }

  assert {
    condition     = github_actions_organization_secret_repositories.portfolio_app_private_key[0].secret_name == "PORTFOLIO_APP_PRIVATE_KEY"
    error_message = "Expected the repository access to target PORTFOLIO_APP_PRIVATE_KEY."
  }

  assert {
    condition     = length(github_actions_organization_secret_repositories.portfolio_app_private_key[0].selected_repository_ids) == length(var.consumer_repositories)
    error_message = "Expected one selected repository ID per consumer repository."
  }

  assert {
    condition     = github_actions_organization_secret.portfolio_app_private_key[0].selected_repository_ids == null
    error_message = "The deprecated selected_repository_ids argument must not return to the secret; repository access belongs to github_actions_organization_secret_repositories."
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
    app_node_id          = "A_kwDOexample"
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

  assert {
    condition     = length(github_actions_organization_secret_repositories.portfolio_app_private_key) == 0
    error_message = "Expected no organisation secret repository access in user mode."
  }
}

# The bypass names the App by its node ID. The provider would resolve a
# "/<slug>" entry as a user login, which an App slug isn't (issue #501).
run "branch_bypass_uses_app_node_id" {
  command = plan

  variables {
    organization         = "example-org"
    enable_branch_bypass = true
    app_node_id          = "A_kwDOexample"
  }

  assert {
    condition = alltrue([
      for k in ["example-repo::develop", "example-repo::master"] :
      one(github_branch_protection.bypass[k].restrict_pushes[0].push_allowances) == "A_kwDOexample"
    ])
    error_message = "Expected the App node ID as the only push allowance on every bypass entry."
  }
}

# Both guards fire: owner_check, and the precondition on the bypass
# resource itself, which also covers `apply -target`.
run "branch_bypass_needs_app_node_id" {
  command = plan

  variables {
    organization         = "example-org"
    enable_branch_bypass = true
    app_node_id          = ""
  }

  expect_failures = [
    terraform_data.owner_check,
    github_branch_protection.bypass,
  ]
}

# A node ID of the `<slug>[bot]` user isn't the App's node ID.
run "app_node_id_refuses_bot_user_id" {
  command = plan

  variables {
    organization         = "example-org"
    enable_branch_bypass = true
    app_node_id          = "BOT_kgDOERMNrQ"
  }

  expect_failures = [
    var.app_node_id,
  ]
}

run "app_node_id_refuses_slug" {
  command = plan

  variables {
    organization         = "example-org"
    enable_branch_bypass = true
    app_node_id          = "example-portfolio-bot"
  }

  expect_failures = [
    var.app_node_id,
  ]
}

# app_slug is optional and no longer read by the module.
run "app_slug_is_optional" {
  command = plan

  variables {
    organization         = "example-org"
    app_slug             = ""
    enable_branch_bypass = true
    app_node_id          = "MDM6QXBwMTIzNDU2Nw=="
  }

  assert {
    condition     = length(github_branch_protection.bypass) == 2
    error_message = "Expected the bypass to plan without app_slug."
  }
}
