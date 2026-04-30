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
    uses: nolte/gh-plumbing/.github/workflows/reusable-pre-commit.yaml@develop
```

!!! tip "Required status check"
    Combine the workflow with a branch-protection rule that requires the `static / Static CI Tests` check—see [Settings](../probot/settings.md).

---

## Central configuration

```yaml title=".github/workflows/reusable-pre-commit.yaml"
{%
   include "../../.github/workflows/reusable-pre-commit.yaml"
%}
```
