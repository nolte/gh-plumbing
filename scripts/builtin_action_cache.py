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
what it resolves to, so it is a finding, as in checkout_credentials.py. Every
occurrence of a duplicated key counts, not only the first. A YAML merge key
(`<<`) on a matched step or in its `with:` is a finding too: `yaml.compose`
doesn't resolve it, so the guard can't see which inputs it brings in. `uses:`
is matched the way the runner resolves it -- split on `/` and `\\`, empty
segments dropped, case-insensitive.

A step that needs one of these caches has to be rebuilt as split
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
  * a step whose `uses:` itself comes in through a merge key: the selector
    never sees it.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

PATTERN = "reusable-pre-commit.yaml"
MERGE_KEY = "<<"
# Longest value from the scanned file echoed into a finding.
ECHO_LIMIT = 60

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


def mapping_all(node: yaml.Node | None, key: str) -> list[tuple[yaml.Node, yaml.Node]]:
    """Every (key node, value node) pair for `key` in a mapping node.

    All of them, not the first: a duplicated key must not hide a later value.
    """
    if not isinstance(node, yaml.MappingNode):
        return []
    return [
        (key_node, value_node) for key_node, value_node in node.value
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key
    ]


def mapping_get(node: yaml.Node | None, key: str) -> tuple[yaml.Node, yaml.Node] | None:
    """Return the first (key node, value node) pair for `key` in a mapping node."""
    pairs = mapping_all(node, key)
    return pairs[0] if pairs else None


def scalar(node: yaml.Node | None) -> str | None:
    return node.value if isinstance(node, yaml.ScalarNode) else None


def is_false(node: yaml.Node | None) -> bool:
    value = scalar(node)
    return value is not None and value.strip().lower() == "false"


def normalise(action: str) -> str:
    """The action as the runner resolves it: split on `/` and `\\`, empty segments dropped.

    actions/runner (PipelineTemplateConverter) does the same, so
    `actions/setup-node/@v6`, `actions//setup-node@v6` and `actions\\setup-node@v6`
    all name `actions/setup-node`. Owner and repository names are
    case-insensitive on GitHub.
    """
    segments = [s for s in re.split(r"[/\\]", action.strip()) if s]
    return "/".join(segments).lower()


def rule_for(uses: str) -> tuple[str, dict[str, str]] | None:
    action, _, ref = uses.partition("@")
    if not ref:
        return None
    return next(((name, rule) for name, rule in RULES.items() if normalise(action) == name), None)


def escape_data(value: str) -> str:
    """Escape a workflow-command message, so no input can start a command line."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    """Escape a workflow-command property value (`file=...`)."""
    return escape_data(value).replace(":", "%3A").replace(",", "%2C")


def echoed(value: str | None) -> str:
    """A value read from the file, shortened before it goes into a message."""
    text = "<not a scalar>" if value is None else value
    return text if len(text) <= ECHO_LIMIT else text[:ECHO_LIMIT] + "..."


REBUILD = (f"A step that needs this cache must be rebuilt as split "
           f"actions/cache/restore + actions/cache/save steps; see {PATTERN}.")


def check_input(action: str, key: str, state: str, with_nodes: list[yaml.Node],
                step_line: int) -> list[tuple[int, str]]:
    """Return (line, message) for every occurrence of `key` that breaks `state`."""
    pairs = [pair for node in with_nodes for pair in mapping_all(node, key)]
    if not pairs:
        if state == "false":
            return [(step_line, (
                f"`{action}` without `with.{key}: false`; the default caches and saves "
                f"in the post step, after the job's later steps ran. {REBUILD}"))]
        return []
    results = []
    for key_node, value_node in pairs:
        line = key_node.start_mark.line + 1
        value = echoed(scalar(value_node))
        if state == "absent":
            results.append((line, (
                f"`{action}` sets `with.{key}: {value}`; its post step saves that cache "
                f"after the job's later steps ran. {REBUILD}")))
        elif not is_false(value_node):
            results.append((line, (
                f"`{action}` sets `with.{key}: {value}`, not a literal `false`; its post "
                f"step would save that cache after the job's later steps ran. {REBUILD}")))
    return results


def check_merge_keys(action: str, step: yaml.Node, with_nodes: list[yaml.Node]) -> list[tuple[int, str]]:
    """A YAML merge key hides what it brings in from this guard: refuse it."""
    results = []
    for where, node in [("the step", step)] + [("`with:`", n) for n in with_nodes]:
        for key_node, _ in mapping_all(node, MERGE_KEY):
            results.append((key_node.start_mark.line + 1, (
                f"`{action}` step with a YAML merge key (`<<`) in {where}; this guard "
                "can't see which inputs it brings in. Write the inputs out.")))
    return results


def audit_steps(path: Path, job: str, steps: yaml.Node) -> list[dict]:
    findings = []
    if not isinstance(steps, yaml.SequenceNode):
        return findings
    for step in steps.value:
        # Every `uses:` of the step, so a duplicated key can't hide the action.
        uses_values = [scalar(value) for _, value in mapping_all(step, "uses")]
        matched = next(
            (rule for rule in (rule_for(u) for u in uses_values if u) if rule), None)
        if matched is None:
            continue
        action, rule = matched
        with_nodes = [value for _, value in mapping_all(step, "with")]
        results = check_merge_keys(action, step, with_nodes)
        for key, state in rule.items():
            results += check_input(action, key, state, with_nodes, step.start_mark.line + 1)
        findings += [finding(path, line, job, message) for line, message in results]
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
        rel = escape_property(str(Path(f["path"]).relative_to(args.root)))
        message = escape_data(f"job {echoed(f['job'])}: {f['message']}")
        print(f"::error file={rel},line={f['line']}::{message}")
    if not findings:
        print(f"No {', '.join(RULES)} step in {args.root} turns on its built-in cache.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
