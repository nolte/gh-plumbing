#!/usr/bin/env python3
"""Refuse an `actions/checkout` step that leaves `persist-credentials` implicit.

`actions/checkout` defaults to `persist-credentials: true`: the job token stays
on the runner for every later step of the job, in a file `.git/config`
includes, where any third-party action or tool that runs afterwards can read
it. #469 fixed that for the pre-commit reusable; #471 found the same default on
20 of the remaining checkout steps. Fixing those sites fixes them once. This
script refuses the class.

Predicate (spec/project/defect-class-guards §G3): EVERY step whose `uses:` is
`actions/checkout@<ref>`, in every workflow under `.github/workflows/` and every
composite action under `.github/actions/`,

  * sets `with.persist-credentials` explicitly -- a missing key is the
    implicit `true` this guard exists to refuse;
  * when the value is anything but `false` (a literal `true`, or an
    expression that may resolve to it), carries a YAML comment -- on the key's
    own line or in the comment lines directly above it -- that names a later
    step of the same job by its `name:`. That is the step that needs the
    credential; a reader, and a reviewer of a later change to that step, can
    then tell why the token is still on the runner.

Selector (§G6): the step's `uses:` value, not a list of files or jobs, so a
checkout added to any workflow is covered without anyone opting it in.

Not covered: checkouts inside third-party actions, and clones done by hand in
a `run:` step. Neither is an `actions/checkout` step in this repository's
files.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

CHECKOUT = re.compile(r"^actions/checkout@", re.IGNORECASE)
KEY = "persist-credentials"


def finding(path: Path, line: int, job: str, message: str) -> dict:
    return {"path": str(path), "line": line, "job": job, "message": message}


def mapping_get(node: yaml.Node, key: str) -> tuple[yaml.Node, yaml.Node] | None:
    """Return the (key node, value node) pair for `key` in a mapping node."""
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if isinstance(key_node, yaml.ScalarNode) and key_node.value == key:
            return key_node, value_node
    return None


def scalar(node: yaml.Node | None) -> str | None:
    return node.value if isinstance(node, yaml.ScalarNode) else None


def comment_for(lines: list[str], index: int) -> str:
    """The comment text attached to line `index`: trailing, then the block above."""
    parts = []
    trailing = re.search(r"\s#\s?(.*)$", lines[index])
    if trailing:
        parts.append(trailing.group(1))
    above = []
    cursor = index - 1
    while cursor >= 0 and lines[cursor].lstrip().startswith("#"):
        above.insert(0, lines[cursor].lstrip()[1:].strip())
        cursor -= 1
    return " ".join(above + parts)


def audit_steps(path: Path, lines: list[str], job: str, steps: yaml.Node) -> list[dict]:
    findings = []
    if not isinstance(steps, yaml.SequenceNode):
        return findings
    for position, step in enumerate(steps.value):
        uses = scalar((mapping_get(step, "uses") or (None, None))[1])
        if uses is None or not CHECKOUT.match(uses):
            continue
        line = step.start_mark.line + 1
        with_pair = mapping_get(step, "with")
        pair = mapping_get(with_pair[1], KEY) if with_pair else None
        if pair is None:
            findings.append(finding(
                path, line, job,
                f"`{capped(uses.split('@')[0])}` without an explicit `with.{KEY}`; the default "
                "persists the job token for every later step. Set `false`, or `true` "
                "with a comment naming the step that needs it."))
            continue
        key_node, value_node = pair
        value = scalar(value_node)
        if value is not None and value.strip().lower() == "false":
            continue
        later = [
            scalar((mapping_get(s, "name") or (None, None))[1])
            for s in steps.value[position + 1:]
        ]
        later = [name for name in later if name]
        comment = comment_for(lines, key_node.start_mark.line)
        if not any(name in comment for name in later):
            findings.append(finding(
                path, key_node.start_mark.line + 1, job,
                f"`{KEY}: {value}` without a comment naming the later step that needs "
                "the credential (by its `name:`)."))
    return findings


def audit_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    root = yaml.compose(text)
    if root is None:
        return []
    lines = text.splitlines()
    findings = []
    jobs = mapping_get(root, "jobs")
    if jobs and isinstance(jobs[1], yaml.MappingNode):
        for job_key, job in jobs[1].value:
            steps = mapping_get(job, "steps")
            if steps:
                findings += audit_steps(path, lines, job_key.value, steps[1])
    runs = mapping_get(root, "runs")
    if runs:
        steps = mapping_get(runs[1], "steps")
        if steps:
            findings += audit_steps(path, lines, "(composite)", steps[1])
    return findings


def candidate_files(root: Path) -> list[Path]:
    files = []
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files += [p for p in workflows.iterdir() if p.suffix in (".yml", ".yaml")]
    # Composite actions live under `.github/actions/` or the top-level
    # `actions/` (nolte/gh-plumbing#488).
    for actions in (root / ".github" / "actions", root / "actions"):
        if actions.is_dir():
            files += [p for p in actions.rglob("action.y*ml") if p.suffix in (".yml", ".yaml")]
    return sorted(files)


def audit(root: Path) -> list[dict]:
    findings = []
    for path in candidate_files(root):
        try:
            findings += audit_file(path)
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            # Fail closed, without echoing the file: a parser's message can
            # quote a line of it (#492).
            findings.append(finding(path, 0, "-", f"could not be read or parsed ({type(exc).__name__}); "
                                                  "nothing in it was checked."))
    return findings


# Output in the runner's command format (#492). Job keys, `uses:` values and
# paths are repository text: in an annotation they are escaped the way the
# runner unescapes them, so a line break can't end the annotation and start a
# command of its own; in a plain log line control characters become '?' and
# '##[' -- the runner's older command syntax, read anywhere in a line --
# becomes '#?['. Echoed values are capped.
CAP = 200


def capped(value: str) -> str:
    return value if len(value) <= CAP else value[:CAP] + "..."


def escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def escape_property(value: str) -> str:
    return escape_data(capped(value)).replace(":", "%3A").replace(",", "%2C")


def shown(value: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", capped(value)).replace("##[", "#?[")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repository root (default: this script's repository)")
    args = parser.parse_args(argv)
    findings = audit(args.root)
    for f in findings:
        rel = Path(f["path"]).relative_to(args.root).as_posix()
        location = f"file={escape_property(rel)}" + (f",line={f['line']}" if f["line"] else "")
        message = "job " + capped(f["job"]) + ": " + f["message"]
        print(f"::error {location}::{escape_data(message)}")
    if not findings:
        print(f"Every actions/checkout step in {shown(str(args.root))} decides {KEY} explicitly.")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
