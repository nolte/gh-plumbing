# Static tests

Runs a minimal static analysis bundle on every pull request and on every push to the default branch to give fast feedback without external services.

- [`pre-commit`](https://pre-commit.com), installed at a pinned version, runs the hooks defined in `.pre-commit-config.yaml` on all files; [`actions/cache`](https://github.com/actions/cache), pinned to a full commit SHA, caches the hook environments (see [Hook environment cache](#hook-environment-cache))

---

## Usage

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  pull_request:
  push:
    branches: [develop] # replace with your default branch

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
```

!!! tip "Required status check"
    Combine the workflow with a branch-protection rule that requires the `static / Static CI Tests` check—see [Settings](../probot/settings.md).

!!! warning "Fork pull requests need the `pull_request` trigger"
    A fork never pushes to the base repository. With a push-only trigger the required check never reports on a pull request from a fork, so that pull request stays blocked. `pull_request_target` isn't an alternative. By default it checks out the base branch, so the required check passes without testing the pull request's changes. Checking out the pull request's head instead runs the fork's code with the base repository's write token and secrets. On a fork pull request `reusable-trivy.yaml` skips uploading its scan report to the Security tab, because the token there has read-only access.

---

## Fork guard

Required checks such as `static / Static CI Tests` run on `pull_request`, and GitHub runs a `pull_request` workflow from the pull request's merge commit. On a fork pull request, the workflow files and the scripts they call come from the fork. A fork can therefore edit them until every job passes. A required context names only the app and the check, so a check the fork defines satisfies it.

`reusable-fork-guard.yaml` is the check a fork can't rewrite. Call it from a `pull_request_target` workflow and require its context next to the others:

```yaml title=".github/workflows/fork-guard.yaml"
on:
  pull_request_target:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read

jobs:
  fork-guard:
    permissions:
      contents: read
      statuses: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-fork-guard.yaml@<tag>
```

The workflow posts its verdict as the commit status `fork-guard`, and that status is the context to require. The check fails when the pull request comes from a fork and adds, changes, removes, or renames a protected path. By default those are `.github/*`, `scripts/*`, `actions/*`, the Taskfile and `taskfiles/*`, `.pre-commit-config.yaml`, any `requirements*.txt`, the pytest and coverage configuration files, and `mkdocs.yml`. Pass `protected-paths` to replace the list. Each line is a bash pattern, and `*` also matches `/`. A pull request from a branch of the same repository passes. To land a legitimate fork change to a protected path, a maintainer re-pushes it to a branch of the repository.

!!! warning "Why `pull_request_target` is safe here"
    `pull_request_target` runs the definition from the default branch, so the pull request can't change the check or its list. The workflow checks out nothing and reads no file content. It lists the changed file names through the compare API and matches them as plain strings. Its only write scope is `statuses`, for posting the verdict. Don't add a checkout to it.

!!! warning "Require the status, not the check run"
    The job's own check run has the name `fork-guard / Protected Paths`. Don't require that name: a fork can add a workflow with a job of the same name that passes, and the same app then reports both check runs. A fork can't post a commit status, because the token of its `pull_request` run has read-only access.

!!! info "Rolling out the context"
    `pull_request_target` runs the workflow file from the base branch. Merge the workflow before, or together with, the change that makes its context required. Branch protection changes only when the settings reach the default branch, and by then the workflow is there.

---

## Hook environment cache

The workflow caches `~/.cache/pre-commit`, where pre-commit installs the hook environments. The cache key combines the runner's operating system release, the installed pre-commit version, the Python installation path, and a hash of `.pre-commit-config.yaml`. A new Ubuntu image behind `ubuntu-latest` or a new pre-commit version therefore starts a fresh cache instead of restoring environments built for another system.

Restoring and saving are separate steps. The workflow saves the cache only in a `pull_request` run, only on a cache miss, and before `pre-commit run` executes any hook. A cache saved by a pull request run is visible to that pull request only. Runs on the default branch, pushes to other branches, and `pull_request_target` runs restore at most and never save. This keeps hook code from writing hook environments into the default branch's cache, which every branch of the repository restores from.

!!! info "Fewer cache hits"
    The default branch never receives a saved cache. Runs on the default branch and the first run of each pull request install the hook environments from scratch, and the next run of the same pull request restores them. A caller that triggers the workflow only on `push` never uses the cache.

!!! warning "Residual risk"
    Hook code runs on the runner and can read the token the runner uses for the cache service. With it, hook code can still write any cache entry in the current run's scope, which on the default branch is the default branch's scope. Splitting restore and save doesn't close this path. Only running the hooks isolated from the runner, for example in a container without the runner context, does.

---

## Docker Hub rate limits

A hook declared with `language: docker_image` pulls its image on every run, and pre-commit can't cache it: that language sets `ENVIRONMENT_DIR = None` with `install_environment = no_install`, so the image stays in the Docker daemon's store and never reaches `~/.cache/pre-commit`, the only path this workflow hands to `actions/cache`.

An anonymous pull counts against a budget that belongs to the source IP address, and GitHub-hosted runners share egress addresses across the platform. The lane therefore spends a budget that every other repository on the same runner network also spends, so a rate-limit rejection can redden a required check for a reason unrelated to the diff.

Two optional parameters move the count to a per-account budget:

| Parameter | Kind | Default | Purpose |
| --- | --- | --- | --- |
| `dockerhub-username` | input | `""` | Docker Hub account name. A username isn't secret, so it travels as an input. Empty skips the login step. |
| `dockerhub-token` | secret | unset | Docker Hub personal access token for that account. It must have the "Public Repo Read-only" scope, because pre-commit hooks in the same job can read it. |

Create the token on a dedicated Docker ID used only by CI (a bot account), not a personal one, give it an expiration date, and rotate it. Hook code can read the token, so a leak then spends only that account's pull quota and exposes no identity you use elsewhere. For the same reason the workflow doesn't persist the checkout token (`persist-credentials: false`). A hook that fetches from `origin` therefore works only in a public repository, and a private consumer needs a workflow of its own.

```yaml title=".github/workflows/build-static-tests.yaml"
jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
    with:
      dockerhub-username: ${{ vars.DOCKERHUB_USERNAME }}
    secrets:
      dockerhub-token: ${{ secrets.DOCKERHUB_TOKEN }}
```

!!! info "Both parameters are optional"
    A caller that passes neither runs exactly as it did before they existed: the login step is skipped and the pulls stay anonymous. A repository whose `.pre-commit-config.yaml` declares no `language: docker_image` hook has nothing to gain from setting them.

!!! warning "A broken credential degrades, it doesn't fail"
    The login step carries `continue-on-error`, so an expired token, a token withheld from a fork's pull request, or a username set without a token all fall back to anonymous pulls and emit a warning annotation. Failing instead would redden the required lane on every pull request, which is worse than the rate limit the login avoids. The run log always states which mode it used.

!!! question "Why not mirror the images to GHCR?"
    Pointing the hooks at a mirror needs an `entry:` override, which decouples the image tag from the hook's `rev:`. That `rev:` is the pin the update automation watches, so the mirror would age unwatched.

---

## Shell lint

`reusable-shellcheck.yaml` lints shell scripts with [ShellCheck](https://www.shellcheck.net/). The workflow installs one fixed ShellCheck release and verifies its checksum before running it, so the version changes only with a release of this repository. It checks every matching file, not only the files a pull request changes, and reports each finding as an annotation: an error, a warning, or a notice for the `info` and `style` levels. It needs `contents: read` only and writes nothing to the pull request.

```yaml title=".github/workflows/build-static-tests.yaml"
jobs:
  shellcheck:
    permissions:
      contents: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-shellcheck.yaml@<tag>
```

| Input | Default | Purpose |
| --- | --- | --- |
| `fail_level` | `error` | Severity at which the job fails: `error`, `warning`, `info`, `any`, or `none`. The job annotates findings below it without failing. |
| `path` | `.` | Base directory to search, one per line. A path that doesn't exist fails the job. |
| `pattern` | `*.sh` | File name pattern of the scripts, one per line. |
| `exclude` | `*/.git/*` | Path pattern to leave out, one per line. A value replaces the default. |
| `check_all_files_with_shebangs` | `false` | Also lint every file whose first line names `sh`, `bash`, `dash`, or `ksh` as its interpreter, whatever the file's name. |
| `shellcheck_flags` | `--external-sources` | Flags for ShellCheck, split on spaces and line ends. The workflow sets the output format itself. |

The job passes when no file matches. A repository without shell scripts can therefore call the workflow before it has any.

The workflow delivers no artifact, so the same call works as a gate in a release path. Put it in front of the publishing job with `needs:`, and a finding at or above `fail_level` stops the publication:

```yaml title=".github/workflows/release-publish.yml"
jobs:
  shellcheck:
    permissions:
      contents: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-shellcheck.yaml@<tag>
  publish:
    needs: shellcheck
    permissions:
      contents: write
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-publish.yml@<tag>
```

!!! info "Scripts in workflow files"
    The workflow reads script files only. `reusable-actionlint.yaml` covers the shell in the `run:` blocks of workflow files.

---

## Central configuration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../../.github/workflows/reusable-pre-commit.yaml"
%}
```
