# Shared Probot Configuration


{%
   include-markdown "../README.md"
   start="<!--probot-intro-start-->"
   end="<!--probot-intro-end-->"
%}

Example:

```yaml
_extends: gh-plumbing:.github/boring-cyborg.yml
```

The Reusable configurations are prefixed with ```.github/commons-*.yml```.


### Shared Configuration

{%
   include-markdown "../README.md"
   start="<!--td-probot-apps-start-->"
   end="<!--td-probot-apps-end-->"
%}

#### Project Settings

For Central Project Configuration we use the [settings](https://probot.github.io/apps/settings/) GitHub App.

This Applications will be handle:

* Default Branch Configuration
* Project Description, topic etc.
* Label Colors


##### Usage

```yaml
_extends: gh-plumbing:.github/commons-settings.yml
repository:
  name: cookiecutter-gh-project
  description: Template for Create Github Workflows and Projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

#### Labelling

For Handle PR and Issue Labels we use [boring-cyborg](https://probot.github.io/apps/boring-cyborg/) for setting labels by Existing roles, like changes at `./docs` always get the Label `documentations`.

##### Usage

```yaml
{%
   include "../.github/boring-cyborg.yml"
%}
```

##### Labelling Rules

```yaml
{%
   include "../.github/commons-boring-cyborg.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```

##### Existing Labels

```yaml
{%
   include "../.github/commons-settings.yml"
   start="# <!--td-commons-settings-labels-start-->"
   end="# <!--td-commons-settings-labels-end-->"
%}
```
The labels will be pre-configured by use the [Settings](#project-settings) GitHub Application.
