# Pull-request lint

Checks a pull request's title and body against the portfolio's pull-request workflow spec (`spec/project/pull-request-workflow/` in `nolte/claude-shared`):

- the Conventional-Commits title, with a type in `feat`, `fix`, `chore`, `docs`, `exp`
- the five required body sections in order, and non-empty Summary, Changes, and Testing
- a `## Class sweep` section on every `fix` pull request
- `Originating source:` and `Dispatched specialist:` in `## Risk / rollout notes` when `## Linked issues` references an issue carrying the audit label
- optionally, a `Refs spec/<topic>/<slug>/` line when the change touches paths outside `spec/`

A pull request from an approved dependency bot gets the title check only.

---

## Usage

```yaml title=".github/workflows/pr-lint.yml"
on:
  pull_request:
    types: [opened, edited, synchronize, ready_for_review]

permissions:
  contents: read

jobs:
  pr-lint:
    permissions:
      contents: read
      pull-requests: read
      issues: read
    uses: nolte/gh-plumbing/.github/workflows/reusable-pr-lint.yaml@<tag-or-commit-sha>
    with:
      spec-anchor: false
```

The caller has to grant `pull-requests: read` and `issues: read`: a called workflow can't widen what its caller grants.

| Input | Default | Effect |
|---|---|---|
| `python-version` | `3.14` | Python for the checker |
| `audit-label` | `audit` | Label that marks an audit tracking issue; empty disables the traceability rule |
| `spec-anchor` | `false` | Require a `Refs spec/…` line when paths outside `spec/` change |

!!! tip "Required status check"
    Require the `pr-lint / PR Lint` context on `develop`; the name joins the caller's job ID and this workflow's job name. See [Settings](../probot/settings.md).

!!! note "The checker runs at the pinned commit"
    The workflow checks out its own checker at the commit the caller pinned, through `job.workflow_repository` and `job.workflow_sha`. It never checks out the caller's repository, so a pull request can't change the rules it's judged by.

---

## Central configuration

```yaml title=".github/workflows/reusable-pr-lint.yaml"
{%
   include "../../../.github/workflows/reusable-pr-lint.yaml"
%}
```
