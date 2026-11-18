#!/usr/bin/env python3
"""Refuse a setup action whose built-in cache saves after the job's commands ran.

Some setup actions carry a cache of their own: they restore it in their main
step and save it in their post step. A post step runs after every later step
of the job -- caller-supplied install and test commands, third-party actions
-- so anything those ran could have rewritten the cached path by the time it
is saved, and on a default-branch run the save lands in the default branch's
cache scope, which every branch restores from. #472 and #476 fixed this for
combined `actions/cache` steps (the `no-combined-actions-cache` pre-commit
hook refuses those); #494 found the same shape in `actions/setup-node`, whose
`package-manager-cache` input defaults to true and caches npm's store whenever
the caller's package.json names npm as its package manager. This script
refuses the class for the setup actions this repository uses.

Predicate: EVERY step, in every workflow under `.github/workflows/` and every
composite action under `.github/actions/` or `actions/`, whose `uses:` is

  * `actions/setup-node@<ref>` sets `with.package-manager-cache` to a literal
    `false` -- a missing key is the implicit `true` -- and sets no
    `with.cache`;
  * `actions/setup-python@<ref>` sets no `with.cache` (it caches only when
    asked, so absence is the safe state);
  * `terraform-linters/setup-tflint@<ref>` sets `with.cache` to nothing but a
    literal `false` (its default).

An expression (`${{ ... }}`) is not a literal `false`: the guard can't tell
what it resolves to, so it is a finding, as in checkout_credentials.py. A step
that needs one of these caches has to be rebuilt as split
`actions/cache/restore@` + `actions/cache/save@` steps that save before any
untrusted command runs and only outside the default branch;
`reusable-pre-commit.yaml` is the pattern.

Selector: the step's `uses:` value, not a list of files or jobs, so such a
step added to any workflow is covered without anyone opting it in.

Not covered:

  * other actions with a cache of their own. `aquasecurity/trivy-action`
    (input `cache`, default true, a combined `actions/cache` step inside the
    action) is a known open one; a new action with such an input needs a
    rule in RULES, or it passes unseen.
  * caches saved inside third-party actions' own steps, and caches written
    by hand from a `run:` step.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

PATTERN = "reusable-pre-commit.yaml"

# action (without @ref) -> {input: required state}
#   "false"  : the input must be present and a literal false
#   "absent" : the input must not be set at all
#   "off"    : the input may be missing or a literal false, nothing else
RULES: dict[str, dict[str, str]] = {
    "actions/setup-node": {"package-manager-cache": "false", "cache": "absent"},
    "actions/setup-python": {"cache": "absent"},
    "terraform-linters/setup-tflint": {"cache": "off"},
}


def finding(path: Path, line: int, job: str, message: str) -> dict:
    return {"path": str(path), "line": line, "job": job, "message": message}


def mapping_get(node: yaml.Node | None, key: str) -> tuple[yaml.Node, yaml.Node] | None:
    """Return the (key node, value node) pair for `key` in a mapping node."""
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return key_node, value_node
    return None


def scalar(node: yaml.Node | None) -> str | None:
    return node.value if isinstance(node, yaml.ScalarNode) else None


def is_false(node: yaml.Node | None) -> bool:
    value = scalar(node)
    return value is not None and value.strip().lower() == "false"


def rule_for(uses: str) -> tuple[str, dict[str, str]] | None:
    action, _, ref = uses.partition("@")
    if not ref:
        return None
    for name, rule in RULES.items():
        if action.strip().lower() == name:
            return name, rule
    return None


def check_input(action: str, key: str, state: str, with_node: yaml.Node | None,
                step_line: int) -> tuple[int, str] | None:
    """Return (line, message) when `key` breaks `state`, else None."""
    pair = mapping_get(with_node, key)
    rebuild = (f"A step that needs this cache must be rebuilt as split "
               f"actions/cache/restore + actions/cache/save steps; see {PATTERN}.")
    if pair is None:
        if state == "false":
            return step_line, (
                f"`{action}` without `with.{key}: false`; the default caches and saves "
                f"in the post step, after the job's later steps ran. {rebuild}")
        return None
    key_node, value_node = pair
    line = key_node.start_mark.line + 1
    value = scalar(value_node)
    if state == "absent":
        return line, (
            f"`{action}` sets `with.{key}: {value}`; its post step saves that cache "
            f"after the job's later steps ran. {rebuild}")
    if is_false(value_node):
        return None
    return line, (
        f"`{action}` sets `with.{key}: {value}`, not a literal `false`; its post step "
        f"would save that cache after the job's later steps ran. {rebuild}")


def audit_steps(path: Path, job: str, steps: yaml.Node) -> list[dict]:
    findings = []
    if not isinstance(steps, yaml.SequenceNode):
        return findings
    for step in steps.value:
        uses = scalar((mapping_get(step, "uses") or (None, None))[1])
        matched = rule_for(uses) if uses else None
        if matched is None:
            continue
        action, rule = matched
        with_node = (mapping_get(step, "with") or (None, None))[1]
        for key, state in rule.items():
            result = check_input(action, key, state, with_node, step.start_mark.line + 1)
            if result:
                findings.append(finding(path, result[0], job, result[1]))
    return findings


def audit_file(path: Path) -> list[dict]:
    root = yaml.compose(path.read_text(encoding="utf-8"))
    if root is None:
        return []
    findings = []
    jobs = mapping_get(root, "jobs")
    if jobs and isinstance(jobs[1], yaml.MappingNode):
        for job_key, job in jobs[1].value:
            steps = mapping_get(job, "steps")
            if steps:
                findings += audit_steps(path, job_key.value, steps[1])
    runs = mapping_get(root, "runs")
    if runs:
        steps = mapping_get(runs[1], "steps")
        if steps:
            findings += audit_steps(path, "(composite)", steps[1])
    return findings


def candidate_files(root: Path) -> list[Path]:
    files = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files += [p for p in workflows.iterdir() if p.suffix in (".yml", ".yaml")]
    for actions in (root / ".github" / "actions", root / "actions"):
        if actions.is_dir():
            files += [p for p in actions.rglob("action.y*ml") if p.suffix in (".yml", ".yaml")]
    return sorted(files)


def audit(root: Path) -> list[dict]:
    findings = []
    for path in candidate_files(root):
        findings += audit_file(path)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: this script's repository)")
    args = parser.parse_args(argv)
    findings = audit(args.root)
    for f in findings:
        rel = Path(f["path"]).relative_to(args.root)
        print(f"::error file={rel},line={f['line']}::job {f['job']}: {f['message']}")
    if not findings:
        print(f"No {', '.join(RULES)} step in {args.root} turns on its built-in cache.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
