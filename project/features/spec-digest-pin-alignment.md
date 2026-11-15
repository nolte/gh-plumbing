---
id: F-6
title: Align the spec corpus on digest pins for portfolio workflow references
status: ready
roadmap_item: R-4
sprint: 2
created: 2026-11-15
ended: null
verifies_sprint_value: null
consistency_check:
  performed_at: 2026-11-15
  agent_version: feature-consistency-reviewer@3845114
  findings:
    - kind: overlap
      target: F-1
      resolution: proceed
      evidence: "reusable-workflow-adoption.md:39-44 (acceptance-1 '...@<tag>', acceptance-2 'Consumers pin to tags, not to @develop')"
    - kind: overlap
      target: F-3
      resolution: proceed
      evidence: "github-actions-best-practices/en.md:194 (OQ: no linter enforces the criteria; scanner adoption unresolved); F-3 adopts zizmor for unpinned-uses only"
    - kind: overlap
      target: F-4
      resolution: proceed
      evidence: "F-4 and F-6 both edit claude-shared spec/project/github-actions-best-practices/{en,de}.md; F-4 adds a post-publish rule, F-6 edits §A and the Open Questions"
    - kind: drift
      target: claude-shared spec/project/workflow-health/en.md:72
      resolution: proceed
      evidence: "workflow-health/en.md:72 (MUST keep gh-plumbing references pinned to a release tag); wording companions :13, :37, :87, :89, :90, :120, :136"
    - kind: drift
      target: claude-shared spec/project/project-structure/en.md:52
      resolution: proceed
      evidence: "project-structure/en.md:52 (SHOULD pin every reusable-workflow reference to a tag, e.g. @v1.1.12)"
    - kind: drift
      target: claude-shared spec/project/release-automation/en.md:148
      resolution: proceed
      evidence: "release-automation/en.md:148 (AC: uses: ...reusable-release-publish.yml@<tag>)"
    - kind: drift
      target: claude-shared spec/project/github-actions-best-practices/en.md:42
      resolution: proceed
      evidence: "en.md:42 and AC :145 scope digest pins to third-party actions; AC :146 accepts any immutable reference, which with :45 still admits a tag"
    - kind: drift
      target: claude-shared spec/project/branching-model/en.md:71
      resolution: proceed
      evidence: "branching-model/en.md:71 (bump cadence for the pinned tag; each repository pins the latest validated tag)"
    - kind: drift
      target: F-6 acceptance-1 scope
      resolution: proceed
      evidence: "project-structure/en.md:137 (Renovate preset #<tag>); taskfile/en.md:43; portfolio-inherited-spec-layer/en.md:179; release-automation/en.md:113 are non-uses: own-org pins outside F-3's audit"
    - kind: drift
      target: claude-shared skills/project-structure-apply/references/operations.md:74
      resolution: proceed
      evidence: "operations.md:74-79 scaffolds callers at @<tag> with an @develop fallback; examples/02-claude-plugin-github-config.md:48-53"
    - kind: drift
      target: claude-shared skills/workflow-health-triage/SKILL.md:76
      resolution: proceed
      evidence: "SKILL.md:76, :132, :145 define and remediate stale pins tag-to-tag; examples/02-stale-pin-portfolio-gap.md:14, :46"
    - kind: drift
      target: claude-shared agents/cicd-pipeline-reviewer.md:89
      resolution: proceed
      evidence: "cicd-pipeline-reviewer.md:89 flags only third-party tags and branch-pinned reusables; skills/cicd-pipeline-design/SKILL.md:84, :132"
    - kind: drift
      target: gh-plumbing docs/en/getting-started/index.md:47
      resolution: proceed
      evidence: "docs/en/getting-started/index.md:47-52 recommends @develop and @vX.Y.Z; 24 docs files match; owned by F-3 acceptance-5"
    - kind: drift
      target: project/roadmap.md (R-4)
      resolution: proceed
      evidence: "R-4 listed four features and requirements R1-R8 at review time; fixed by the fifth R-4 checklist bullet and R9"
    - kind: prior-art
      target: claude-shared spec/project/workflow-health/en.md:134
      resolution: proceed
      evidence: "workflow-health/en.md:134 accepts a digest whose trailing comment names the release tag; github-actions-best-practices/en.md:42-43 digest plus version comment"
    - kind: drift
      target: claude-shared spec/project/dockerfile-best-practices/en.md:46
      resolution: proceed
      evidence: "dockerfile-best-practices/en.md:46, :58 tag-pinned third-party actions; tracked in nolte/claude-shared#743, outside F-6"
    - kind: prior-art
      target: claude-shared spec/claude/skill-agent-catalog/en.md:120
      resolution: proceed
      evidence: "skill-agent-catalog/en.md:120 cites reusable-mkdocs.yaml@v1.1.19 descriptively, not as a pin rule"
---

## Description

In `nolte/claude-shared`, the spec corpus today requires or allows a bare tag for
`nolte/gh-plumbing` and own-organization `uses:` references, while F-3 makes
every such reference fail CI. F-6 changes each of those rules to one pin shape:
a full-length commit digest with a trailing comment naming the release tag. It
drops the own-org tag exemption in `github-actions-best-practices` §A, and
narrows the Open Question about workflow-scanning tools to the criteria that
stay unenforced.

The skills and agents that encode the old rule follow the spec: a repository
scaffolded or reviewed by them gets digest-pinned callers. A workflow author
reading any of these specs finds one consistent answer, and that answer passes
the shared `actionlint` check.

Known sites, re-read on 2026-11-15:

- `github-actions-best-practices/en.md`: `:42`, `:45`, `:48`, AC `:145`, `:146`, Open Questions `:191`, `:194`
- `release-automation/en.md`: `:40`, AC `:148`, `:149`
- `project-structure/en.md`: `:52`, AC `:143`
- `branching-model/en.md`: `:70`, `:71`
- `workflow-health/en.md`: `:72`, AC `:134` (drop the bare-tag alternative), wording `:13`, `:37`, `:87`, `:89`, `:90`, `:120`, `:136`
- `skills/project-structure-apply/references/operations.md:74-79` and `examples/02-claude-plugin-github-config.md:48-53`
- `skills/workflow-health-triage/SKILL.md:76`, `:132`, `:145` and `examples/02-stale-pin-portfolio-gap.md:14`, `:46`
- `agents/cicd-pipeline-reviewer.md:89`, `skills/cicd-pipeline-design/SKILL.md:84`, `:132`

## Acceptance criteria

- [ ] **acceptance-1** No spec rule or acceptance criterion under `spec/project/` in `nolte/claude-shared` accepts a bare tag or a branch for a workflow `uses:` reference to `nolte/gh-plumbing` or another own-organization action or reusable workflow.
- [ ] **acceptance-2** Every amended site requires a full-length commit digest with a trailing comment naming the release tag for those `uses:` references.
- [ ] **acceptance-3** The own-org tag exemption in `github-actions-best-practices` §A is gone, Open Question `:191` is closed, and Open Question `:194` states that pinning is enforced by `zizmor` in the shared `actionlint` reusable while the other criteria stay unenforced.
- [ ] **acceptance-4** The DE translation of every amended spec is structurally in sync with the EN source.
- [ ] **acceptance-5** No skill or agent in `nolte/claude-shared` scaffolds, recommends, or accepts a bare-tag or branch `uses:` reference to `nolte/*`; `project-structure-apply` no longer falls back to `@develop`.

## Test hooks

- **acceptance-1**: `grep -rnE "nolte/gh-plumbing/[^ ]+@(<tag>|v[0-9]|develop)|pinned to a (release )?tag" spec/project` in `nolte/claude-shared`, every remaining hit reviewed as non-`uses:` or descriptive; pending
- **acceptance-2**: manual review of each listed site; pending
- **acceptance-3**: manual review of `github-actions-best-practices/en.md` §A and Open Questions; pending
- **acceptance-4**: `spec` skill drift check in `nolte/claude-shared`; pending
- **acceptance-5**: grep over `skills/` and `agents/` for the same pattern, plus a dry run of `project-structure-apply` on a scratch repository; pending

## Consistency notes

**Overlap with F-1, proceed.** Established:
`project/features/reusable-workflow-adoption.md:39-44` states the adoption
contract as a tag pin, and F-6 replaces the tag pin in the spec. F-1 is `done`
and anchors the mission's `verifies_via`, so superseding it would break the
mission and sprint 1 traceability, and merging into a terminal feature isn't
possible. Its contract survives in substance: a digest whose trailing comment
names the release tag still resolves to that published tag, which
`workflow-health/en.md:134` already accepts. F-1's wording stays as the
historical record of the contract at the time it was verified.

**Overlap with F-3, proceed.** Established:
`github-actions-best-practices/en.md:194` asks whether to adopt a
workflow-scanning tool for all of the spec's criteria. F-3, now on disk, adopts
`zizmor` for `unpinned-uses` only, so F-6 narrows that question to the
unenforced criteria rather than closing it (acceptance-3). The two features
live in different repositories and share no acceptance criterion; F-6 governs
the rule, F-3 its enforcement. The reviewer proposed `revisit-after` because
F-3 wasn't on disk yet; that condition has been met.

**Overlap with F-4, proceed.** Established: both edit
`github-actions-best-practices/{en,de}.md` in `nolte/claude-shared`. F-4 adds a
post-publish metadata rule; F-6 edits §A, the acceptance criteria `:145` and
`:146`, and the Open Questions. They share no acceptance-criterion subject.
Merging them would tie F-4, which the requirements mark as independent, to the
F-3 release schedule, so they stay separate and only their PR order needs
coordinating.

**Drift: further spec sites.** Established, re-read at the cited lines:
`workflow-health/en.md:72` (MUST pin to a release tag), `project-structure/en.md:52`
(SHOULD pin to a tag), `release-automation/en.md:148` (AC with `@<tag>`),
`github-actions-best-practices/en.md:146`, and `branching-model/en.md:71` were
missing from the first site list. They're in the list above. The reviewer
reports that DE line numbers mirror the EN ones for these files (unestablished
by this author; acceptance-4's drift check settles it). Resolution: proceed.

**Drift: scope of acceptance-1.** Reported by the reviewer:
`project-structure/en.md:137` (Renovate preset `#<tag>`), `taskfile/en.md:43`,
`portfolio-inherited-spec-layer/en.md:179`, and `release-automation/en.md:113`
pin own-org artefacts outside workflow `uses:`. F-3's audit doesn't check them,
so acceptance-1 and acceptance-2 are limited to workflow `uses:` references.
Resolution: proceed.

**Drift: skills and agents.** Established for
`skills/project-structure-apply/references/operations.md:74-79`, which scaffolds
callers at `@<tag>` and falls back to `@develop`. Reported by the reviewer for
`workflow-health-triage` (stale pin defined tag-to-tag) and for
`cicd-pipeline-reviewer` and `cicd-pipeline-design` (flag only third-party tags
and branch-pinned reusable workflows). Freshly scaffolded repositories would fail F-3's
check, so acceptance-5 covers them in this feature rather than a separate one.
Resolution: proceed.

**Drift: gh-plumbing consumer docs.** Established: a grep for
`nolte/gh-plumbing/...@(tag|develop)` matches 24 files under gh-plumbing's
`docs/`, including `docs/en/getting-started/index.md:47-52`, which recommends
`@develop`. That's gh-plumbing content, owned by F-3 acceptance-5. Resolution:
proceed.

**Drift: roadmap and requirements trace.** Established at review time: R-4
listed four features and the requirements stopped at R8. R-4 now carries a fifth
checklist bullet and the requirements carry strand E with R9. Resolution:
proceed.

**Prior art: the target pin shape exists.** Established:
`workflow-health/en.md:134` already accepts a digest whose trailing comment
names the release tag, and `github-actions-best-practices/en.md:42-43` asks for
digest plus version comment for third-party actions. F-6 extends that rule
rather than inventing one. Resolution: proceed.

**Side finding: tag-pinned examples in `dockerfile-best-practices`.**
Established: `dockerfile-best-practices/en.md:46` and `:58` reference
`docker/metadata-action@v6` and `docker/build-push-action@v7`. That already
violates §A for third-party actions and is outside F-6's own-org scope; tracked
in `nolte/claude-shared`#743. Resolution: proceed.

**Prior art: descriptive version citation.** Reported by the reviewer:
`spec/claude/skill-agent-catalog/en.md:120` cites `reusable-mkdocs.yaml@v1.1.19`
as a description, not a pin rule. No change needed. Resolution: proceed.

## Risks

- **Ordering.** F-6 has to be released in `nolte/claude-shared` no later than the
  gh-plumbing release that ships F-3; otherwise spec-conformant consumers and
  freshly scaffolded repositories fail CI with no spec to point them at.
- F-4 and F-6 edit the same spec files; their PRs must land in sequence to
  avoid conflicting Open Questions edits.
- The `workflow-health` wording sites talk about "tag bumps" throughout; leaving
  any of them unchanged reads as tag-pin doctrine even after the MUSTs move.

## References

- `project/requirements/release-archive-provenance.md` R9
- nolte/gh-plumbing#446, `nolte/claude-shared`#743
