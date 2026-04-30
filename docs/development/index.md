# Development

Local development setup for contributing to `gh-plumbing` itself.

---

## Tooling

The project pins its tools with [asdf](https://asdf-vm.com/) (`.tool-versions`).

```sh
asdf install
```

This installs `act`, `python`, and `task` at the pinned versions.

---

## Common tasks

The shared [nolte/taskfiles](https://github.com/nolte/taskfiles) collection provides the task definitions.

```sh
task -l
```

=== "Pre-commit"

    ```sh
    task pre-commit:install   # register hooks
    task pre-commit:start     # run against all files
    ```

=== "Documentation"

    ```sh
    task mkdocs:start         # serve on http://localhost:8001
    ```

!!! note "Without task"
    If you prefer raw commands:

    ```sh
    virtualenv ~/.vens/development
    source ~/.vens/development/bin/activate
    pip install -r requirements-dev.txt
    mkdocs serve -a localhost:8001
    ```

---

## Running workflows locally

Use [nektos/act](https://github.com/nektos/act) to execute GitHub Actions on your machine:

```sh
act push -j static -W .github/workflows/build-static-tests.yaml
```

---

## Prose linting

[Vale](https://vale.sh/) lints Markdown files in CI via `reusable-spelling-vale.yaml`. Rules live in `.vale.ini` and styles under `.github/styles/`.

!!! info "CLAUDE.md is excluded"
    `CLAUDE.md` carries LLM context, not end-user documentation—Vale explicitly skips it.
