# Plumbing

[![GitHub Project Stars](https://img.shields.io/github/stars/nolte/gh-plumbing.svg?label=Stars&style=social)](https://github.com/nolte/gh-plumbing) [![GitHub Issue Tracking](https://img.shields.io/github/issues-raw/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![GitHub LatestRelease](https://img.shields.io/github/release/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![.github/workflows/build-static-tests.yaml](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) [![.github/workflows/release-cd-deliver-docs.yml](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml)

---

<!--intro-start-->
Centralised reusable [GitHub Actions workflows](https://docs.github.com/en/actions) and shared [GitHub App](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps) configurations, so downstream projects can avoid duplicating CI/CD boilerplate.
<!--intro-end-->

## Workflows

<!--td-workflows-start-->
| Workflow                                      | description                                                                                                                                                      |
|-----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```reusable-ansible-galaxy-push.yaml```      | Publish an Ansible role to [Ansible Galaxy](https://galaxy.ansible.com/) via [robertdebock/galaxy-action](https://github.com/robertdebock/galaxy-action).        |
| ```reusable-ansible-molecule.yaml```         | Run a [Molecule](https://molecule.readthedocs.io/) test scenario via [gofrolist/molecule-action](https://github.com/gofrolist/molecule-action).                  |
| ```reusable-automerge.yaml```                | Auto-merge pull requests via [pascalgn/automerge-action](https://github.com/pascalgn/automerge-action).                                                          |
| ```reusable-chain-bench.yaml```              | Run the supply-chain CIS (Center for Internet Security) benchmark via [aquasecurity/chain-bench-action](https://github.com/aquasecurity/chain-bench-action).     |
| ```reusable-dependency-review.yaml```        | Gate pull requests against vulnerable or licence-incompatible dependency changes via [actions/dependency-review-action](https://github.com/actions/dependency-review-action). |
| ```reusable-docker-lint-build.yaml```        | Run [hadolint](https://github.com/hadolint/hadolint-action) on a Dockerfile and a buildx dry-build (no push) for fast PR feedback.                              |
| ```reusable-docker-publish.yaml```           | Build a multi-arch container image with [docker/build-push-action](https://github.com/docker/build-push-action) and push it to a configurable OCI registry.      |
| ```reusable-mkdocs.yaml```                   | Build and publish an [mkdocs](https://www.mkdocs.org/) site to [GitHub Pages](https://pages.github.com/).                                                        |
| ```reusable-pre-commit.yaml```               | Run [pre-commit](https://pre-commit.com/) for a minimal static-test bundle (linters, formatters, EditorConfig).                                                  |
| ```reusable-release-cd-refresh-master.yml``` | Fast-forward `master` to the latest published release tag so `master` always represents the latest release.                                                      |
| ```reusable-release-drafter.yml```           | Update the open draft release with a changelog from merged PRs via [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter).        |
| ```reusable-release-publish.yml```           | Promote an open release-drafter draft to a published release for a given tag, with an optional dry-run validation gate.                                          |
| ```reusable-spelling-vale.yaml```            | Lint Markdown prose via [errata-ai/vale-action](https://github.com/errata-ai/vale-action) with inline reviewdog annotations on pull requests.                    |
| ```reusable-sphinx.yaml```                   | Build and publish a [Sphinx](https://www.sphinx-doc.org/en/master) documentation site to [GitHub Pages](https://pages.github.com/).                              |
| ```reusable-stale.yaml```                    | Mark and close stale issues and pull requests via [actions/stale](https://github.com/actions/stale).                                                             |
| ```reusable-trivy.yaml```                    | Scan the repository with [aquasecurity/trivy-action](https://github.com/aquasecurity/trivy-action).                                                              |
| ```reusable-tf-lint.yaml```                  | Lint Terraform sources with [terraform-linters/setup-tflint](https://github.com/terraform-linters/setup-tflint).                                                 |

<!--td-workflows-end-->


## Probot configuration

<!--probot-intro-start-->
Collection of common configurations for project management and CI/CD.  
Reuse this shared set of Probot configurations across your GitHub projects. For more information, see the [Probot best-practices documentation](https://probot.github.io/docs/best-practices/#configuration).
<!--probot-intro-end-->

<!--td-probot-apps-start-->
| probot                                                            | git                                                                         | description                                                                                                         |
|-------------------------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| [boring-cyborg](https://probot.github.io/apps/boring-cyborg/)     | [kaxil/boring-cyborg](https://github.com/kaxil/boring-cyborg)               | Automates pull-request labelling and other repository housekeeping tasks.                                            |
| [release-drafter](https://probot.github.io/apps/release-drafter/) | [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) | Creates a human-readable release changelog (**deprecated** as a Probot app—prefer the workflow implementation).     |
| [renovate](https://github.com/apps/renovate)                      |                                                                             | Keeps dependencies in sync with [Renovate](https://www.whitesourcesoftware.com/free-developer-tools/renovate/), an automated dependency-update bot. |
| [settings](https://probot.github.io/apps/settings/)               | [probot/settings](https://github.com/probot/settings)                       | Configure GitHub Projects by Source.                                                                                |
<!--td-probot-apps-end-->

For more information, see the [gh-plumbing GitHub Pages site](http://nolte.github.io/gh-plumbing).

## Development

<!--development-intro-start-->
Use the [asdf](https://asdf-vm.com/) package manager.

```sh
asdf install
```

### Workflows

For local testing, use [nektos/act](https://github.com/nektos/act) to run the GitHub Actions on your machine.

```sh
act push -j static -W .github/workflows/build-static-tests.yaml
```

This runs the [`build-static-tests`](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) workflow on your machine.


### Documentation

```sh
virtualenv ~/.vens/development

source ~/.vens/development/bin/activate
pip install -r requirements-dev.txt

mkdocs serve -a localhost:8001
```

Open [localhost:8001](http://localhost:8001/) to view the latest documentation, built with [mkdocs](https://www.mkdocs.org/).
<!--development-intro-end-->

### Task

Use [go-task/task](https://github.com/go-task/task) as pre-configured command sets.

```sh
task -l  

task: Available tasks for this project:
* mkdocs:start:             mkdocs serve docs
* pre-commit:install:       install pre-commit into current project
* pre-commit:start:         run pre-commit with all files

```
shared tasks from [nolte/taskfiles](https://github.com/nolte/taskfiles)

## Links

* [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project) for templating.
