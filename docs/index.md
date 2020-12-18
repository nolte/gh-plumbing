# Shared Probot Configs

For Using in other Github Projects use the Probot Repo Config, more informations at [probot.github.io](https://probot.github.io/docs/best-practices/#configuration).

Example:

```ỳaml
_extends: gh-plumbing:.github/commons-stale.yml
```

The Reuseable configurations are prefixed with ```.github/commons-*.yml```.


### Shared Configs

#### Project Settings

For Central Project Configuration we use the [settings](https://probot.github.io/apps/settings/) Github App.

This Applications will be handle:

* Default Branch Configuration
* Project Description, topic etc.
* Label Colors


##### Usage

```
_extends: gh-plumbing:.github/commons-settings.yml
repository:
  name: cookiecutter-gh-project
  description: Template for Create Github Workflows and Projects
  homepage: https://nolte.github.io/cookiecutter-gh-project
  topics: templating, cookiecutter, github
```

#### Labelling

For Handle PR and Issue Labels we use a combination of Two Github Applications, [stale](https://probot.github.io/apps/stale/) for close Inactive Elements, and [boring-cyborg](https://probot.github.io/apps/boring-cyborg/) for setting labels by Existing roles, like changes at `./docs` allways get the Label `documentations`.

##### Usage
