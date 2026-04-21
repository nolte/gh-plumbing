# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

`gh-plumbing` is a **configuration-only** repository (no application code). It centralizes two kinds of assets so downstream GitHub projects can consume them and avoid boilerplate:

1. **Reusable GitHub Actions workflows** — `.github/workflows/reusable-*.y{a}ml`, called from other repos via `uses: nolte/gh-plumbing/.github/workflows/reusable-<name>.yaml@develop`.
2. **Shared Probot / tool configurations** — `.github/commons-*.yml` (consumed via Probot's `_extends:` mechanism) and `renovate-configs/common.json` (consumed via `github>nolte/gh-plumbing//renovate-configs/common`).

Changes here propagate automatically to every repo that references them. Treat every edit as a public API change.

## Branching & release flow

- Default branch is **`develop`** — all reusable workflows self-reference `@develop` (see `build-static-tests.yaml`, `release-cd-refresh-master.yml`).
- `master` is **auto-refreshed on every published release** by `reusable-release-cd-refresh-master.yml` (merges the release tag into master). Do not commit to `master` directly; it always represents the latest release.
- `release-drafter` maintains the draft changelog as PRs land on `develop`.
- Branch protection (per `commons-settings.yml`) requires the `static / Static CI Tests` check on `develop`.

## Common commands

The repo uses **asdf** for tool pinning (`.tool-versions`: act, python, task).

```sh
asdf install                                   # install pinned tool versions
task -l                                        # list tasks (pulled from nolte/taskfiles)
task pre-commit:install                        # install pre-commit hooks
task pre-commit:start                          # run pre-commit on all files
task mkdocs:start                              # serve docs at localhost:8001

# Local workflow runs (act):
act push -j static -W .github/workflows/build-static-tests.yaml

# Docs (manual, without task):
virtualenv ~/.vens/development
source ~/.vens/development/bin/activate
pip install -r requirements-dev.txt
mkdocs serve -a localhost:8001
```

`Taskfile.yml` pulls includes from `https://raw.githubusercontent.com/nolte/taskfiles/fix/py-var-names/src` — task definitions live in that external repo, not here.

## Architecture notes

### Reusable workflow pattern

Non-reusable workflows (`build-static-tests.yaml`, `release-cd-refresh-master.yml`, `release-drafter.yml`, `automerge.yaml`, `stale.yaml`, `spelling.yaml`, `dependency-review.yaml`) are thin callers that only wire secrets/inputs into the `reusable-*` counterpart. When adding functionality, put the logic in the `reusable-*` file so downstream repos get it too; the non-reusable wrapper is this repo's own dog-fooding consumer.

### Shared Probot configs (`_extends`)

`.github/settings.yml`, `.github/boring-cyborg.yml`, `.github/release-drafter.yml` each use `_extends: gh-plumbing:.github/commons-<name>.yml`. Downstream repos do the same. Editing a `commons-*.yml` file changes behavior for every consumer — the local `settings.yml` / `boring-cyborg.yml` / `release-drafter.yml` only contain repo-specific overrides.

### Docs composition

`mkdocs.yml` uses the `include-markdown` plugin. `docs/*.md` files pull snippets from `README.md` via delimiter comments (`<!--intro-start-->`, `<!--td-workflows-start-->`, `<!--development-intro-start-->`, `<!--probot-intro-start-->`, `<!--td-probot-apps-start-->`). **Keep those markers intact** when editing the README — removing or renaming them breaks the generated site.

### Prose linting

Vale is configured in `.vale.ini` with styles in `.github/styles/` (Microsoft, RedHat, nolte-styles). It runs through `reusable-spelling-vale.yaml`. Pre-commit only covers whitespace/YAML; prose rules apply only in CI.
