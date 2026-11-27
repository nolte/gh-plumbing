# Requirements: Reusable ShellCheck workflow

<!--
Produced via the `requirements-elicit` skill, following
spec/project/requirements-elicitation/.
`c_d` is an uncertainty proxy (self-consistency-derived), not a calibrated
probability. A requirement is `confirmed` only after an explicit teach-back.
-->

Elicited 2026-11-27 with the repository owner, as work step 1 of
`.resume/reusable-shellcheck/plan.md`.

## Bounded context

- **What:** a new reusable workflow `.github/workflows/reusable-shellcheck.yaml`
  that lints a consumer repository's shell scripts with ShellCheck; a
  dog-fooding job in `build-static-tests.yaml`; documentation in the README
  workflow table and in `docs/en` and `docs/de`.
- **For whom:** maintainers of gh-plumbing consumer repositories, who call it
  in CI and as a gate in a release path; and this repository itself.
- **Out of scope:** packaging or delivering an artifact; making the job a
  required check in `.github/settings.yml`; a `.shellcheckrc`; a pre-commit
  hook; linting `run:` blocks (stays with `reusable-actionlint.yaml`); a
  ShellCheck job in this repository's `release-publish.yml`.

## Understanding KPI

- Thresholds: `τ_low = 0.4`, `τ_high = 0.8`, self-consistency `k = 2`, question budget = `6` (5 used)
- `U_gate = min_d c_d` over required dimensions = **0.85**
- Termination: `saturation`

### Gap matrix

| Dimension | Applicable | `c_d` | Uncertainty source | Evidence event |
|---|---|---|---|---|
| `functional` | yes | 0.9 | specification | answers on `fail_level`, shebang switch; closing teach-back on the input set |
| `non_functional` | yes | 0.85 | interpretation | closing teach-back (all files, annotations, `contents: read`) |
| `constraints` | yes | 0.9 | interpretation | plan design decision of 2026-11-27; action source read at v1.35.1 |
| `domain_objects` | yes | 0.9 | interpretation | closing teach-back on inputs and their defaults |
| `actors` | yes | 0.9 | interpretation | bounded-context teach-back |
| `acceptance_criteria` | yes | 0.85 | specification | closing teach-back, item 4 |
| `edge_cases` | yes | 0.85 | specification | answers on shebang-only scripts and the empty run; `k = 2` sketches (empty run green versus red) diverged until answered |
| `scope_boundaries` | yes | 0.9 | specification | bounded-context teach-back; answer on the release gate |

## Requirements

- **R1**: WHEN a consumer calls `reusable-shellcheck.yaml`, the workflow SHALL
  run ShellCheck through `reviewdog/action-shellcheck`, pinned by commit SHA,
  over every matching file, not only over changed files (`filter_mode: nofilter`).
  - _dimension_: `functional` · _status_: `confirmed` · _source_: plan design decision 2; teach-back item 2
- **R2**: The workflow SHALL expose the inputs `fail_level` (default `error`),
  `path` (default `.`), `pattern` (default `*.sh`), `exclude` (default
  `*/.git/*`), `check_all_files_with_shebangs` (default `false`) and
  `shellcheck_flags` (default `--external-sources`).
  - _dimension_: `domain_objects` · _status_: `confirmed` · _source_: teach-back item 1
- **R3**: WHEN ShellCheck reports a finding at or above `fail_level`, the job
  SHALL fail; WHEN every finding is below `fail_level`, the job SHALL pass and
  show the findings as annotations.
  - _dimension_: `functional` · _status_: `confirmed` · _source_: answer on `fail_level`, option `error`
- **R4**: WHEN `check_all_files_with_shebangs` is `true`, the workflow SHALL
  also lint files that carry a shell shebang without matching `pattern`.
  - _dimension_: `edge_cases` · _status_: `confirmed` · _source_: answer on shebang-only scripts, option "input, default off"
- **R5**: WHEN no file matches, the job SHALL pass.
  - _dimension_: `edge_cases` · _status_: `confirmed` · _source_: teach-back item 3
- **R6**: The workflow SHALL declare `contents: read` only, check out with
  `persist-credentials: false`, and report findings as workflow-command
  annotations (`reporter: github-annotations`).
  - _dimension_: `non_functional` · _status_: `confirmed` · _source_: plan design decision 2; teach-back item 2
- **R7**: The workflow SHALL be usable unchanged from a pre-merge workflow and
  as a `needs:` gate in a release path; it SHALL deliver no artifact.
  - _dimension_: `functional` · _status_: `confirmed` · _source_: plan design decision 1
- **R8**: `build-static-tests.yaml` SHALL call the workflow by local path in a
  `shellcheck` job; the job SHALL NOT become a required check.
  - _dimension_: `scope_boundaries` · _status_: `confirmed` · _source_: plan design decision 3
- **R9**: The README workflow table and `docs/en` and `docs/de` SHALL describe
  the workflow with a CI caller example and a release-gate `needs:` example in
  the `@<tag>` form; this repository's `release-publish.yml` SHALL stay unchanged.
  - _dimension_: `scope_boundaries` · _status_: `confirmed` · _source_: answer on the release gate, option "documented example only"
- **R10**: The work is accepted WHEN the dog-fooding job runs green on the
  pull request, a deliberately broken script demonstrably turns it red, and
  the documentation of R9 is in place.
  - _dimension_: `acceptance_criteria` · _status_: `confirmed` · _source_: teach-back item 4

## Surviving assumptions / open risks

- **Open conflict, R3 against R1 (observed 2026-11-27):** on a pull-request
  event, a finding below `fail_level` that ShellCheck can fix automatically
  fails the job. Run 46065761938 on pull request #519, with an info-level
  SC2086 probe and `fail_level: error`, ended with `found at least one issue
  with severity greater than or equal to the given level: error`. The cause is
  the action's second "suggestion" pass: it feeds `shellcheck -f diff` to
  `reviewdog` with a hard-coded `github-pr-review` reporter, diff diagnostics
  carry no severity, and `reviewdog` v0.21.3 fails on an unknown severity for
  every `fail_level` other than `none`. The same pass tries to post a review
  to the pull request and is refused with 403 under `contents: read`. On push
  events the pass exits early and R3 holds (observed in `act` runs). The
  action has no input that turns the pass off, so R1 and R3 can't both hold
  as written; the operator decides which one gives.
- **Fact, not an assumption:** the action pins ShellCheck `0.11.0` and
  `reviewdog` `v0.21.3` itself; its only nested action reference
  (`reviewdog/action-setup` v1.5.0) is pinned by commit SHA.
