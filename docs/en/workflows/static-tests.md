# Static tests

Runs a minimal static analysis bundle on every push to give fast feedback without external services.

- [`pre-commit/action`](https://github.com/pre-commit/action) runs hooks defined in `.pre-commit-config.yaml`
- [`zbeekman/EditorConfig-Action`](https://github.com/zbeekman/EditorConfig-Action) enforces `.editorconfig` rules

---

## Usage

```yaml title=".github/workflows/build-static-tests.yaml"
on:
  push:

jobs:
  static:
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@<tag>
```

!!! tip "Required status check"
    Combine the workflow with a branch-protection rule that requires the `static / Static CI Tests` check—see [Settings](../probot/settings.md).

---

## Docker Hub rate limits

A hook declared with `language: docker_image` pulls its image on every run, and pre-commit can't cache it: that language sets `ENVIRONMENT_DIR = None` with `install_environment = no_install`, so the image stays in the Docker daemon's store and never reaches `~/.cache/pre-commit`, the only path `pre-commit/action` hands to `actions/cache`.

An anonymous pull counts against a budget that belongs to the source IP address, and GitHub-hosted runners share egress addresses across the platform. The lane therefore spends a budget that every other repository on the same runner network also spends, so a rate-limit rejection can redden a required check for a reason unrelated to the diff.

Two optional parameters move the count to a per-account budget:

| Parameter | Kind | Default | Purpose |
| --- | --- | --- | --- |
| `dockerhub-username` | input | `""` | Docker Hub account name. A username isn't secret, so it travels as an input. Empty skips the login step. |
| `dockerhub-token` | secret | unset | Docker Hub access token for that account. A read-only token is enough; nothing here pushes. |

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

## Central configuration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../../.github/workflows/reusable-pre-commit.yaml"
%}
```
