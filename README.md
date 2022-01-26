# Plumbing

<!--intro-start-->
Used for deduplicate the CI/CD Boilerplate-Code. Like [Workflow](https://docs.github.com/en/actions) and [Github App](https://docs.github.com/en/developers/apps/getting-started-with-apps/about-apps) configurations.
<!--intro-end-->

## Workflows

<!--td-workflows-start-->
| Workflow                            | description                                                                                                                                                  |
|-------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| ```reuseable-mkdocs.yaml```         | Publish a [mkdocs](https://www.mkdocs.org/) based Documentation as [Github Page](https://pages.github.com/).                                                 |
| ```reuseable-pre-commit.yaml```     | call [pre-commit](https://pre-commit.com/) for executing a set of Static Tests.                                                                              |
| ```reuseable-release-drafter.yml``` | Will be use [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) for updating the current "Draft" Release with a Changelog. |
| ```reuseable-trivy.yaml```          | Scan the GitRepo by using [aquasecurity/trivy-action](https://github.com/aquasecurity/trivy-action).                                                         |
| ```reuseable-automerge.yaml```      | Using [pascalgn/automerge-action](https://github.com/pascalgn/automerge-action) for better Merge Request handling.                                           |
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
| [release-drafter](https://probot.github.io/apps/release-drafter/) | [toolmantim/release-drafter](https://github.com/toolmantim/release-drafter) | Creates a Human Readable Release Change Log.                                                                        |
| [renovate](https://github.com/apps/renovate)                      |                                                                             | Using [renovate](https://www.whitesourcesoftware.com/free-developer-tools/renovate/) for keep dependencies in sync. |
| [settings](https://probot.github.io/apps/settings/)               | [probot/settings](https://github.com/probot/settings)                       | Configure Github Projects by Source.                                                                                |
<!--td-probot-apps-end-->

For More Inforation take a look to the GH Page, [gh-plumbing](http://nolte.github.io/gh-plumbing).

## Development

<!--development-intro-start-->
We use the [asdf](https://asdf-vm.com/) Packagemanager.


```sh
asdf install

virtualenv ~/.vens/development

source ~/.vens/development/bin/activate
pip install -r requirements-dev.txt

mkdocs serve -a localhost:8001
```

Open [localhost:8001](http://localhost:8001/) for take a look to the lastest documentation, created with [mkdocs](https://www.mkdocs.org/).
<!--development-intro-end-->

## Links

* [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project) for templating.
