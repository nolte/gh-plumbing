# HACS validation

Validates a HACS-distributed Home Assistant custom integration with the two official actions, so a consuming repository inherits the same gate HACS and Home Assistant Core apply.

- [`hacs/action`](https://github.com/hacs/action) runs the same code HACS uses to validate a repository (`hacs.json` existence, brands, topics, …); `category` defaults to `integration`
- [`home-assistant/actions/hassfest`](https://github.com/home-assistant/actions) validates the integration manifest and structure, including custom integrations

---

## Usage

```yaml title=".github/workflows/ci.yml"
on:
  push:
  pull_request:

jobs:
  hacs-validate:
    uses: nolte/gh-plumbing/.github/workflows/reusable-hacs-validate.yaml@develop
```

!!! tip "Custom repository vs. default store"
    Leave `ignore` empty for a default-store-grade run. HACS forbids ignored checks for default-store inclusion. A pure custom repository may ignore checks it can't satisfy, for example `with: { ignore: "brands" }`.

---

## Release ZIP asset

For HACS integrations, [`reusable-release-publish.yml`](release.md) builds a `<domain>.zip` asset from `custom_components/<domain>/` at the release's target commit and attaches it to the draft **before** flipping `draft=false`, so HACS never sees a release without its download. This happens automatically whenever the repository carries a `custom_components/<domain>/manifest.json`; no extra wiring is needed.

The full release-and-distribution contract is specified in [`spec/ha/hacs-release`](https://github.com/nolte/claude-home-assistant/blob/develop/spec/ha/hacs-release/en.md) in `claude-home-assistant`.

---

## Central configuration

```yaml title=".github/workflows/reusable-hacs-validate.yaml"
{%
   include "../../../.github/workflows/reusable-hacs-validate.yaml"
%}
```
