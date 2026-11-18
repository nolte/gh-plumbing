<p align="center">
  <img src=".github/assets/banner.svg" alt="gh-plumbing: reusable GitHub Actions workflows and shared Probot and Renovate configurations" width="100%">
</p>

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
| ```reusable-branch-protection-audit.yaml```  | Compare the branch protection a repository declares in `.github/settings.yml` against what GitHub enforces, across classic protection and rulesets alike.        |
| ```reusable-chain-bench.yaml```              | Run the supply-chain CIS (Center for Internet Security) benchmark via [aquasecurity/chain-bench-action](https://github.com/aquasecurity/chain-bench-action).     |
| ```reusable-dependency-review.yaml```        | Gate pull requests against vulnerable or licence-incompatible dependency changes via [actions/dependency-review-action](https://github.com/actions/dependency-review-action). |
| ```reusable-docs-freshness.yaml```           | Audit a documentation tree for the drift `mkdocs build --strict` can't see: language parity, references to workflows that no longer exist, decision-index hygiene, and leftover placeholders. |
| ```reusable-docker-lint-build.yaml```        | Run [hadolint](https://github.com/hadolint/hadolint-action) on a Dockerfile and a buildx dry-build (no push) for fast PR feedback.                              |
| ```reusable-docker-publish.yaml```           | Build a multi-arch container image with [docker/build-push-action](https://github.com/docker/build-push-action) and push it to a configurable OCI registry.      |
| ```reusable-fork-guard.yaml```               | Fail a fork pull request that changes the workflows, scripts or configuration the required checks run from, from a `pull_request_target` check the fork can't rewrite. |
| ```reusable-hacs-validate.yaml```            | Validate a HACS-distributed Home Assistant custom integration with [hacs/action](https://github.com/hacs/action) and [hassfest](https://github.com/home-assistant/actions) on push and pull request. |
| ```reusable-mkdocs-build.yaml```             | Build an [mkdocs](https://www.mkdocs.org/) site with `--strict` (no deploy) so broken links, missing nav entries, and render errors fail the pull request.       |
| ```reusable-mkdocs.yaml```                   | Build and publish an [mkdocs](https://www.mkdocs.org/) site to [GitHub Pages](https://pages.github.com/).                                                        |
| ```reusable-nodejs-coverage.yaml```          | Run Node.js tests ([Vitest](https://vitest.dev/) or [Jest](https://jestjs.io/)) and render the Istanbul `json-summary` coverage report into the GitHub Actions job summary, with an optional `fail-under` gate. |
| ```reusable-pre-commit.yaml```               | Run [pre-commit](https://pre-commit.com/) for a minimal static-test bundle (the hooks the consumer's `.pre-commit-config.yaml` declares).                                                  |
| ```reusable-pr-lint.yaml```                  | Lint a pull request's Conventional-Commits title and required body sections, the class sweep on `fix`, and remediation traceability on audit-linked pull requests.|
| ```reusable-python-coverage.yaml```          | Run [pytest](https://pytest.org/) with [pytest-cov](https://pytest-cov.readthedocs.io/) and render the coverage report into the GitHub Actions job summary, with an optional `fail-under` gate. |
| ```reusable-release-archive.yml```           | Build a release archive through a Task target, attest its build provenance, and attach it to the release-drafter draft before publish. |
| ```reusable-release-cd-refresh-master.yml``` | Fast-forward `master` to the latest published release tag so `master` always represents the latest release.                                                      |
| ```reusable-release-drafter.yml```           | Update the open draft release with a changelog from merged PRs via [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter).        |
| ```reusable-release-drafter-autolabel.yml``` | Apply the type label a pull request's Conventional-Commits title implies, fork pull requests included, so it lands under one changelog category. |
| ```reusable-release-publish.yml```           | Promote an open release-drafter draft to a published release for a given tag, with an optional dry-run validation gate; for HACS integrations it attaches a `<domain>.zip` asset to the draft before publish. |
| ```reusable-spelling-vale.yaml```            | Lint Markdown prose via [errata-ai/vale-action](https://github.com/errata-ai/vale-action) with inline reviewdog annotations on pull requests.                    |
| ```reusable-sphinx.yaml```                   | Build and publish a [Sphinx](https://www.sphinx-doc.org/en/master) documentation site to [GitHub Pages](https://pages.github.com/).                              |
| ```reusable-stale.yaml```                    | Mark and close stale issues and pull requests via [actions/stale](https://github.com/actions/stale).                                                             |
| ```reusable-trivy.yaml```                    | Scan the repository with [aquasecurity/trivy-action](https://github.com/aquasecurity/trivy-action).                                                              |
| ```reusable-tf-lint.yaml```                  | Lint Terraform sources with [terraform-linters/setup-tflint](https://github.com/terraform-linters/setup-tflint).                                                 |

<!--td-workflows-end-->

## Actions

### `actions/setup-vale`

Installs a pinned [Vale](https://vale.sh/) binary on a Linux x86-64 runner. The action downloads the release asset to `RUNNER_TEMP` and compares it with a committed checksum through `sha256sum -c` before it unpacks anything. It extracts only the `vale` binary, runs it once, and then adds its directory to `PATH`. On a checksum mismatch the action fails and leaves nothing unpacked, run, or on `PATH`. Other runner platforms fail with a message that names the limit.

Pin the action to a full-length commit hash, like every third-party action:

```yaml
steps:
  - uses: actions/checkout@<full-commit-sha> # <release-tag>
    with:
      persist-credentials: false
  - id: vale
    uses: nolte/gh-plumbing/actions/setup-vale@<full-commit-sha> # <release-tag>
  - run: vale --version
```

| Input          | Default         | Description                                                                                                   |
|----------------|-----------------|---------------------------------------------------------------------------------------------------------------|
| `version-file` | `.vale-version` | Path of the version file, relative to the workspace. The action reads it only when `version` and `sha256` are both empty. |
| `version`      | empty           | Vale version as `x.y.z`, without the `v`. Set it together with `sha256`.                                      |
| `sha256`       | empty           | Checksum of `vale_<version>_Linux_64-bit.tar.gz`, 64 hexadecimal digits. Set it together with `version`.      |

| Output         | Description                                                                                               |
|----------------|-----------------------------------------------------------------------------------------------------------|
| `vale-version` | The installed version. Empty unless `result` is `installed`.                                              |
| `result`       | `installed`, or the reason for a failure: `invalid-pin`, `unsupported-platform`, `download-failed`, `checksum-mismatch`, or `run-failed`. |

The action sets `result` on failure too. A step with `continue-on-error: true` can then treat an unreachable download, which says nothing about the asset, differently from a refusal. `reusable-release-publish.yml` does exactly that: a download failure skips its release-notes check with a warning, and a checksum mismatch fails the run before it publishes.

#### The `.vale-version` file

The file holds two keys and comment lines. The format matches the one in [`nolte/claude-shared`](https://github.com/nolte/claude-shared/issues/768), so one file works with both.

```text
# Comment lines start with a hash.
VALE_VERSION=3.15.2
VALE_SHA256=fc72e64454d6bd7af91905d4faebbf411bae3eec17bb572f4101311212bc0d9e  vale_3.15.2_Linux_64-bit.tar.gz
```

The `VALE_SHA256` value is the `Linux_64-bit` line of `vale_<version>_checksums.txt` from the [Vale release](https://github.com/vale-cli/vale/releases), copied verbatim with its two spaces. The action refuses a line that names another version than `VALE_VERSION`. Read the checksum from the release itself, then compare it with the hash of the downloaded asset:

```sh
v=3.15.2
curl -fsSLO "https://github.com/vale-cli/vale/releases/download/v${v}/vale_${v}_checksums.txt"
grep Linux_64-bit "vale_${v}_checksums.txt"
curl -fsSLO "https://github.com/vale-cli/vale/releases/download/v${v}/vale_${v}_Linux_64-bit.tar.gz"
sha256sum "vale_${v}_Linux_64-bit.tar.gz"
```

#### Renovate

The shared preset `renovate-configs/common.json` carries a regex manager for `VALE_VERSION` in `.vale-version`, using the `github-releases` datasource for `vale-cli/vale`. Renovate can't recompute the checksum, so the preset turns automerge off for this bump. A repository's own rules can turn it back on. A bump pull request needs one manual step:

1. Replace the `VALE_SHA256` line with the `Linux_64-bit` line of the new release's checksum file, as the previous section shows.
2. Where `.tool-versions` pins `vale`, set it to the same version. Renovate doesn't bump that line.

Until the first step is done, the action refuses the file. Add a check that runs the action or compares the two versions on pull requests that change `.vale-version`. In this repository, `scripts/vale_version.py` runs as a pre-commit hook and fails while either line disagrees, and `test-setup-vale.yml` runs the action.


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
