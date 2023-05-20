# Plumbing

[![Github Project Stars](https://img.shields.io/github/stars/nolte/gh-plumbing.svg?label=Stars&style=social)](https://github.com/nolte/gh-plumbing) [![Github Issue Tracking](https://img.shields.io/github/issues-raw/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![Github LatestRelease](https://img.shields.io/github/release/nolte/gh-plumbing.svg)](https://github.com/nolte/gh-plumbing) [![.github/workflows/build-static-tests.yaml](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) [![.github/workflows/release-cd-deliver-docs.yml](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/release-cd-deliver-docs.yml)

---

<!--intro-start-->
Used for deduplicate the CI/CD Boilerplate-Code. Like [Workflow](https://docs.github.com/en/actions) and [Github App](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps) configurations.
<!--intro-end-->

## Workflows

<!--td-workflows-start-->
| Workflow                                      | description                                                                                                                                                      |
|-----------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```reuseable-ansible-galaxy-push.yaml```      | Using [robertdebock/galaxy-action](https://github.com/robertdebock/galaxy-action) for publish a Ansible Role to [Ansible Galxy](https://galaxy.ansible.com/).    |
| ```reuseable-ansible-molecule.yaml```         | Start a simple Molecule test run by using the [gofrolist/molecule-action](https://github.com/gofrolist/molecule-action) action.                                  |
| ```reuseable-automerge.yaml```                | Using [pascalgn/automerge-action](https://github.com/pascalgn/automerge-action) for better Merge Request handling.                                               |
| ```reuseable-mkdocs.yaml```                   | Publish a [mkdocs](https://www.mkdocs.org/) based Documentation as [Github Page](https://pages.github.com/).                                                     |
| ```reuseable-pre-commit.yaml```               | Call [pre-commit](https://pre-commit.com/) for a minimal static tests set, like liter etc.                                                                       |
| ```reuseable-release-cd-refresh-master.yml``` | Refresh the current master branch, with the Revision from the Latest published Release, so the master/main branch will be present the `latest` Released version. |
| ```reuseable-release-drafter.yml```           | Will be use [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) for updating the current "Draft" Release with a Changelog.     |
| ```reuseable-sphinx.yaml```                   | Build and Publish a [Sphinx](https://www.sphinx-doc.org/en/master) Documentation as [Github Page](https://pages.github.com/).                                    |
| ```reuseable-stale.yaml```                    | Mark old or inactive issues and close then, used [actions/stale](https://github.com/actions/stale) for this work.                                                |
| ```reuseable-trivy.yaml```                    | Scan the GitRepo by using [aquasecurity/trivy-action](https://github.com/aquasecurity/trivy-action).                                                             |
| ```reuseable-tf-lint.yaml```                  | Use [terraform-linters/setup-tflint](https://github.com/terraform-linters/setup-tflint) for Lint terraform sources.                                              |
<!--td-workflows-end-->

## Probot Config

<!--probot-intro-start-->
Collection of common Configs for Project Management and CI/CD.  
For Using in other Github Projects, having a reuseable set of Probot Config Repo, more informations at [probot.github.io](https://probot.github.io/docs/best-practices/#configuration).
<!--probot-intro-end-->

<!--td-probot-apps-start-->
| probot                                                            | git                                                                         | description                                                                                                         |
|-------------------------------------------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| [boring-cyborg](https://probot.github.io/apps/boring-cyborg/)     | [kaxil/boring-cyborg](https://github.com/kaxil/boring-cyborg)               | Different util actions like, automatically label Pull Request                                                       |
| [release-drafter](https://probot.github.io/apps/release-drafter/) | [toolmantim/release-drafter](https://github.com/toolmantim/release-drafter) | Creates a Human Readable Release Change Log (**(deprecated)**, please use the Workflow Implementation).             |
| [renovate](https://github.com/apps/renovate)                      |                                                                             | Using [renovate](https://www.whitesourcesoftware.com/free-developer-tools/renovate/) for keep dependencies in sync. |
| [settings](https://probot.github.io/apps/settings/)               | [probot/settings](https://github.com/probot/settings)                       | Configure Github Projects by Source.                                                                                |
<!--td-probot-apps-end-->

For More Inforation take a look to the GH Page, [gh-plumbing](http://nolte.github.io/gh-plumbing).

## Development

<!--development-intro-start-->
We use the [asdf](https://asdf-vm.com/) Packagemanager.

```sh
asdf install
```

### Worflows

For local testing you can use [nektos/act](https://github.com/nektos/act), run the GitHub Actions locally.

```sh
act --job=static
```

will be start the [![.github/workflows/build-static-tests.yaml](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/build-static-tests.yaml) at your local system.

**For the Moment blocked by [#826](https://github.com/nektos/act/issues/826)**.

### Documentation

```sh
virtualenv ~/.vens/development

source ~/.vens/development/bin/activate
pip install -r requirements-dev.txt

mkdocs serve -a localhost:8001
```

Open [localhost:8001](http://localhost:8001/) for take a look to the lastest documentation, created with [mkdocs](https://www.mkdocs.org/).
<!--development-intro-end-->

### Task

We use [go-task/task](https://github.com/go-task/task) as alias tooling.

```sh
task -l  

task: Available tasks for this project:
* mkdocs:       Start the Mkdocs, for development
* pre-commit:   Start Precommit
```

## Links

* [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project) for templating.
