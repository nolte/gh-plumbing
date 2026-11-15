# Requirements: Release archive with provenance, plus an unpinned-action guard

<!--
Produced via the `requirements-elicit` skill, following
spec/project/requirements-elicitation/.
`c_d` is an uncertainty proxy (self-consistency-derived), not a calibrated
probability. A requirement is `confirmed` only after an explicit teach-back.
-->

Source issue: [nolte/gh-plumbing#446](https://github.com/nolte/gh-plumbing/issues/446).
Elicited 2026-11-15 with the repository owner as the upstream gate of `roadmap-plan`.

## Bounded context

- **What:** a reusable way for a consumer repository to build an arbitrary,
  Task-built release archive, attest its build provenance, and attach it to the
  release-drafter draft *before* publish; a portfolio check that refuses
  third-party actions not pinned to a commit digest; a best-practices rule that
  post-publish steps don't rewrite release metadata; and the first consumer
  (nolte/vale-style) migrating onto the reusable step.
- **For whom:** maintainers of gh-plumbing consumer repositories; nolte/vale-style
  is the first concrete consumer.
- **Strands (all four in scope, one roadmap item):**
  A: `reusable-release-archive.yml` (gh-plumbing);
  B: pinning check (gh-plumbing);
  C: `spec/project/github-actions-best-practices/` note (`nolte/claude-shared`);
  D: vale-style migration (nolte/vale-style).
- **Out of scope:** repairing the empty release bodies of vale-style v0.1.14 to
  v0.1.17; reworking the HACS asset path in `reusable-release-publish.yml`;
  enabling GitHub immutable releases.

## Understanding KPI

- Thresholds: `τ_low = 0.4`, `τ_high = 0.8`, self-consistency `k = 2`, question budget = `10` (9 used)
- `U_gate = min_d c_d` over required dimensions = **0.85**
- Termination: `saturation`

### Gap matrix

| Dimension | Applicable | `c_d` | Uncertainty source | Evidence event |
|---|---|---|---|---|
| `functional` | yes | 0.9 | specification | Rounds 2, 4, 5 answers; round 9 teach-back confirmed |
| `non_functional` | yes | 0.85 | specification | Round 4 (job-level permissions only, no breaking change); round 9 teach-back |
| `constraints` | yes | 0.85 | interpretation | Round 4 `startup_failure` constraint and round 6 Renovate `pinDigests` rationale; k=2 readings of "generalise in reusable-release-publish" diverged, resolved by round 4 |
| `domain_objects` | yes | 0.9 | interpretation | Draft release, asset glob, attestation, `uses:` reference; round 9 teach-back |
| `actors` | yes | 0.9 | specification | Round 1 (consumer maintainers; vale-style first consumer) |
| `acceptance_criteria` | yes | 0.85 | specification | AC1–AC4 proposed and confirmed in round 9 |
| `edge_cases` | yes | 0.9 | specification | Round 8 table confirmed explicitly (`passt`) |
| `scope_boundaries` | yes | 0.9 | specification | Round 1 (A–D in one item); out-of-scope list confirmed in round 9 |

## Requirements

### Strand A: `reusable-release-archive.yml` (gh-plumbing)

- **R1**: WHEN a consumer calls `reusable-release-archive.yml` with a Task target
  and one or more asset paths or globs, the workflow SHALL run the target at the
  draft tag's target commit, attest every matching file with
  `actions/attest-build-provenance`, and attach every matching file to the draft
  release.
  - _dimension_: `functional` · _status_: `confirmed` · _source_: round 2 "2" (Task target plus multiple paths or glob); round 9 `passt`
- **R2**: The workflow SHALL be a separate reusable that the consumer runs before
  `release-publish`, ordered by `needs:`; `reusable-release-publish.yml` and its
  HACS asset path SHALL stay unchanged.
  - _dimension_: `functional`, `scope_boundaries` · _status_: `confirmed` · _source_: round 3 "1" (HACS stays alongside); round 4 "2" (separate reusable)
- **R3**: `id-token: write` and `attestations: write` SHALL be declared only at
  job level in `reusable-release-archive.yml`; a consumer that builds no archive
  SHALL need no new permission.
  - _dimension_: `non_functional`, `constraints` · _status_: `confirmed` · _source_: round 4 "2"; round 9 `passt`
- **R4a**: WHEN an asset glob matches no file, the workflow SHALL fail before
  any upload, so publish isn't reached.
- **R4b**: WHEN an asset of the same name is already attached to the draft
  (re-run), the workflow SHALL replace it (`gh release upload --clobber`, draft only).
- **R4c**: WHEN attestation fails, the workflow SHALL fail without uploading.
- **R4d**: WHEN `dry-run` is set, the workflow SHALL build and attest but not upload.
- **R4e**: WHEN the target release is already published (no draft), the workflow
  SHALL fail without modifying the release.
  - R4a–R4e: _dimension_: `edge_cases` · _status_: `confirmed` · _source_: round 8 `passt`

### Strand B: Pinning check (gh-plumbing)

- **R5**: `reusable-actionlint.yaml` SHALL run a `zizmor` step with the
  `unpinned-uses` audit that reports, as an error, every external `uses:` not
  pinned to a 40-character commit SHA, with no exemption (`nolte/*`, `actions/*`,
  and `github/*` included). Local `./` references aren't external.
  - _dimension_: `functional`, `constraints` · _status_: `confirmed` · _source_: round 5 "1"; round 6 "3"; round 9 `passt`
- **R6**: The check SHALL fail from the release that ships it, with no warn-only
  phase; red consumer builds are accepted.
  - _dimension_: `non_functional` · _status_: `confirmed` · _source_: round 7 "3"

### Strand C: Spec (`nolte/claude-shared`)

- **R7**: `spec/project/github-actions-best-practices/` SHALL state that steps
  running after publish MUST NOT rewrite release metadata, that
  `gh release upload` without `--clobber` is the safe primitive, and that
  `ncipollo/release-action` with `allowUpdates` needs `omitBodyDuringUpdate` and
  its sibling options.
  - _dimension_: `functional` · _status_: `confirmed` · _source_: issue #446 item 3; round 9 `passt`

### Strand D: Migration of vale-style (nolte/vale-style)

- **R8**: WHEN a gh-plumbing release ships strand A, nolte/vale-style SHALL call
  `reusable-release-archive.yml` with target `build` and asset
  `build/nolte-styles.zip`, and SHALL delete `release-cd-archive.yml`.
  - _dimension_: `functional` · _status_: `confirmed` · _source_: issue #446 proposed change 4; round 9 `passt`

### Acceptance criteria

- **AC1**: A `dry-run` invocation of `reusable-release-archive.yml` in gh-plumbing is green.
- **AC2**: The next vale-style release carries `nolte-styles.zip` at the moment
  of publish, and `gh attestation verify` succeeds for it.
- **AC3**: A deliberately tag-pinned `uses:` turns the `actionlint` check red.
- **AC4**: The vale-style release body survives publish intact.
  - AC1–AC4: _dimension_: `acceptance_criteria` · _status_: `confirmed` · _source_: round 9 `passt`

## Surviving assumptions / open risks

- **Risk: immediate red consumer builds (R5, R6).** Every consumer that bumps to
  the release shipping R5 goes red on its own `nolte/gh-plumbing/...@develop` or
  `@v…` references until they're digest-pinned. Where `actionlint` is a required
  check, the Renovate PR that delivers the bump is itself blocked. Accepted
  deliberately by the owner in round 7.
- **Risk: vale-style lacks `pinDigests`.** It extends
  `renovate-configs/common` at `#v1.1.12`, before the preset gained
  `pinDigests`, so strand B hits it without automated re-pinning (issue #446).
- **Assumption: `zizmor` policy expressiveness.** R5 assumes `zizmor`'s
  `unpinned-uses` audit can be configured to require hash pins for every
  external reference; not yet verified against the `zizmor` version that will be
  pinned.
- **Ordering dependency.** R8 depends on a gh-plumbing release containing A; R7
  is independent of A and B.
