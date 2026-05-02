# Settings

The [Probot Settings App](https://probot.github.io/apps/settings/) syncs repository configuration from version control.

Shared rules cover:

- Default branch, description, topics, homepage
- Issue/PR features (issues, projects, wiki, pages, downloads)
- Merge strategies (`allow_squash_merge`, `allow_merge_commit`, `allow_rebase_merge`)
- `delete_branch_on_merge`
- Branch protection for `master` and `develop`
- Shared label palette

---

## Usage

```yaml title=".github/settings.yml"
_extends: gh-plumbing:.github/commons-settings.yml

repository:
  name: cookiecutter-gh-project
  description: Template for creating GitHub workflows and projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

!!! tip "Overrides"
    Keys in your local `.github/settings.yml` override the inherited values. Only specify what differs from the shared defaults.

---

## Central configuration

```yaml title=".github/commons-settings.yml"
{%
   include "../../.github/commons-settings.yml"
%}
```
