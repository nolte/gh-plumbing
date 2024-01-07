# Plumbing

[![GitHub Project Stars](https://img.shields.io/github/stars/nolte/gh-plumbing.svg?label=Stars&style=social)](https://github.com/nolte/gh-plumbing) [![GitHub Issue Tracking](https://img.shields.io/github/issues-raw/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![GitHub LatestRelease](https://img.shields.io/github/release/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![.github/workflows/build-static-tests.yaml](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) [![.github/workflows/release-cd-deliver-docs.yml](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml)

---

<!--intro-start-->
Used for minimize duplicate the CI/CD Boilerplate-Code. Like [Workflows (GitHub Actions)](https://docs.github.com/en/actions) and [GitHub App](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps) configurations.
<!--intro-end-->

## Workflows

<!--td-workflows-start-->
| Workflow                                      | description                                                                                                                                                      |
|-----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```reusable-ansible-galaxy-push.yaml```      | Using [robertdebock/galaxy-action](https://github.com/robertdebock/galaxy-action) for publish a Ansible Role to [Ansible Galxy](https://galaxy.ansible.com/).    |
| ```reusable-ansible-molecule.yaml```         | Start a simple Molecule test run by using the [gofrolist/molecule-action](https://github.com/gofrolist/molecule-action) action.                                  |
| ```reusable-automerge.yaml```                | Using [pascalgn/automerge-action](https://github.com/pascalgn/automerge-action) for better Merge Request handling.                                               |
| ```reusable-mkdocs.yaml```                   | Publish a [mkdocs](https://www.mkdocs.org/) based Documentation as [GitHub Page](https://pages.github.com/).                                                     |
| ```reusable-pre-commit.yaml```               | Call [pre-commit](https://pre-commit.com/) for a minimal static tests set, like liter etc.                                                                       |
| ```reusable-release-cd-refresh-master.yml``` | Refresh the current master branch, with the Revision from the Latest published Release, so the master/main branch will be present the `latest` Released version. |
| ```reusable-release-drafter.yml```           | Will be use [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) for updating the current "Draft" Release with a Changelog.     |
| ```reusable-sphinx.yaml```                   | Build and Publish a [Sphinx](https://www.sphinx-doc.org/en/master) Documentation as [GitHub Page](https://pages.github.com/).                                    |
| ```reusable-stale.yaml```                    | Mark old or inactive issues and close then, used [actions/stale](https://github.com/actions/stale) for this work.                                                |
| ```reusable-trivy.yaml```                    | Scan the GitRepo by using [aquasecurity/trivy-action](https://github.com/aquasecurity/trivy-action).                                                             |
| ```reusable-tf-lint.yaml```                  | Use [terraform-linters/setup-tflint](https://github.com/terraform-linters/setup-tflint) for Lint terraform sources.                                              |

<!--td-workflows-end-->


## Probot configuration

<!--probot-intro-start-->
Collection of common Configurations for Project Management and CI/CD.  
For Using in other GitHub Projects, having a reusable set of Probot Configuration Repository, more information at [probot.github.io](https://probot.github.io/docs/best-practices/#configuration).
<!--probot-intro-end-->

<!--td-probot-apps-start-->
| probot                                                            | git                                                                         | description                                                                                                         |
|-------------------------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| [boring-cyborg](https://probot.github.io/apps/boring-cyborg/)     | [kaxil/boring-cyborg](https://github.com/kaxil/boring-cyborg)               | Different actions like, automatically label Pull Request                                                       |
| [release-drafter](https://probot.github.io/apps/release-drafter/) | [toolmantim/release-drafter](https://github.com/toolmantim/release-drafter) | Creates a Human Readable Release Change Log (**(deprecated)**, please use the Workflow Implementation).             |
| [renovate](https://github.com/apps/renovate)                      |                                                                             | Using [renovate](https://www.whitesourcesoftware.com/free-developer-tools/renovate/) for keep dependencies in sync. |
| [settings](https://probot.github.io/apps/settings/)               | [probot/settings](https://github.com/probot/settings)                       | Configure GitHub Projects by Source.                                                                                |
<!--td-probot-apps-end-->

For More information take a look to the GH Page, [gh-plumbing](http://nolte.github.io/gh-plumbing).

## Development

<!--development-intro-start-->
Use the [asdf](https://asdf-vm.com/) package manager.

```sh
asdf install
```

### Workflows

For local testing you can use [nektos/act](https://github.com/nektos/act), run the GitHub Actions locally.

```sh
act push -j static -W .github/workflows/build-static-tests.yaml
```

Will be start the [![.github/workflows/build-static-tests.yaml](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) at your system.


### Documentation

```sh
virtualenv ~/.vens/development

source ~/.vens/development/bin/activate
pip install -r requirements-dev.txt

mkdocs serve -a localhost:8001
```

Open [localhost:8001](http://localhost:8001/) for take a look to the latest documentation, created with [mkdocs](https://www.mkdocs.org/).
<!--development-intro-end-->

### Task

Use [go-task/task](https://github.com/go-task/task) as pre-configured command sets.

```sh
task -l  

task: Available tasks for this project:
* mkdocs:       Start the Mkdocs, for development
* pre-commit:   Start Precommit
```

## Links

* [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project) for templating.
