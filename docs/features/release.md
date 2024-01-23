# Release Process

using [release-drafter/release-drafter](https://github.com/release-drafter/release-drafter) for generate tagged release and generated release artefacts. This Action is part of the template Project [nolte/cookiecutter-gh-project](https://github.com/nolte/cookiecutter-gh-project).

## Usage


Two configurations must be created for use. The **GitHub Workflow**, and the **Probot** settings.

### Workflow

```yaml
---
name: Release Drafter

on:
  push:
    branches:
      - develop

jobs:
  update_release_draft:
    uses: nolte/gh-plumbing/.github/workflows/reusable-release-drafter.yml@v1.1.8
    secrets:
      token: ${{ secrets.GITHUB_TOKEN }}

```
*(from `.github/workflows/release-drafter.yml`)*

### Probot

```sh
---
# These settings are synced to GitHub by https://probot.github.io/apps/release-drafter/

_extends: gh-plumbing:.github/commons-release-drafter.yml

```
*(from `.github/release-drafter.yml`)*

take a look to the release draft from this project:

[![.github/workflows/release-drafter.yml](https://github.com/nolte/gh-plumbing/actions/workflows/release-drafter.yml/badge.svg)](https://github.com/nolte/gh-plumbing/actions/workflows/release-drafter.yml)

## Central Configuration

### Workflow

The full Action configuration will be used from a central place.

```yaml
{%
   include "../../.github/workflows/reusable-release-drafter.yml"
%}
```
from `.github/workflows/reusable-release-drafter.yml`.


### Probot

```yaml
{%
   include "../../.github/commons-release-drafter.yml"
%}
```
from `.github/commons-release-drafter.yml`.
