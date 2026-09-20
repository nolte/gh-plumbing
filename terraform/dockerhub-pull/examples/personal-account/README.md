# Personal-account example: Docker-hub-pull module

End-to-end runnable example for a personal GitHub account (no
organisation). The module creates per-repository Actions variables and
secrets instead of organisation-scoped ones.

## Pre-conditions

- A Docker Hub personal access token exists, scoped **Public Repo
  Read-only**. Nothing this credential serves pushes an image, so a
  broader scope only widens what a leak reaches.
- The `GITHUB_TOKEN` environment variable holds a Personal Access Token
  with `repo` scope for the account. `admin:org` isn't needed because
  there is no organisation.
- `TF_VAR_dockerhub_username` and `TF_VAR_dockerhub_token` carry values
  from your local secret manager (not committed, and never in tfvars).

## Run

```sh
export GITHUB_TOKEN=ghp_...
export TF_VAR_dockerhub_username=octocat
export TF_VAR_dockerhub_token="$(gopass show -o internet/hub.docker.com/octocat/ci-pull-token)"

terraform init
terraform plan
terraform apply
```

## What to expect

Two resources per repository in `consumer_repositories`: the Actions
variable `DOCKERHUB_USERNAME` and the Actions secret `DOCKERHUB_TOKEN`.

Nothing in CI changes shape afterwards. A workflow that already passes
the pair into `reusable-pre-commit.yaml` starts authenticating its image
pulls; one that doesn't keeps pulling anonymously. Both are working
states — the credential raises a ceiling, it never becomes a dependency.

## Verifying it took effect

The registry reports the live quota on every pull, so the check is the
run log rather than the Terraform output:

```
Docker Hub login succeeded — pulls are authenticated
```

The reusable workflow prints that line (or the anonymous-mode warning)
on every run, precisely so the mode is stated rather than inferred.
