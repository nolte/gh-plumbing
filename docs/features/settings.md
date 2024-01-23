# Project settings

For Central Project Configuration use the [settings](https://probot.github.io/apps/settings/) GitHub App.

This Applications will be handle:

* Default Branch Configuration
* Project Description, topic etc.
* Label Colors


## Usage

### Probot

```yaml
_extends: gh-plumbing:.github/commons-settings.yml
repository:
  name: cookiecutter-gh-project
  description: Template for Create Github Workflows and Projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

## Central Configuration¶

### Probot

```yaml
{%
   include "../../.github/commons-settings.yml"
%}
```
