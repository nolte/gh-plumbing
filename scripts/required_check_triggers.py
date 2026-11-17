#!/usr/bin/env python3
"""Refuse required status contexts that a fork pull request can never satisfy.

A required context on a protected branch is reported by whichever workflow
runs the job behind it. If that workflow does not run for a fork pull request,
the context never reports there and the pull request stays BLOCKED -- no
error, no failed check, just a merge button that never turns green. Issue #462
was exactly that: `static / Static CI Tests` came from a workflow triggered on
`push` only, and a fork never pushes to this repository.

Fixing that one workflow fixes one site. This script refuses the class.

Predicate (spec/project/defect-class-guards §G3): for EVERY context listed under
`branches[*].protection.required_status_checks.contexts` in
`.github/settings.yml`, at least one non-reusable workflow under
`.github/workflows/` produces it, and every workflow that produces it

  * triggers on `pull_request` -- `pull_request_target` does not count: it
    runs the base ref by default, so the check would go green without testing
    the pull request at all;
  * does not narrow that trigger so the context can go unreported: no `paths`
    or `paths-ignore` filter, no `branches` / `branches-ignore` filter that
    excludes the protected branch, and, where `types` is given, both `opened`
    and `synchronize` among them;
  * grants no `write` scope to the producing job -- the job's own
    `permissions:` block, or the workflow-level one when the job has none.
    A fork pull request's token is read-only, so a producer that needs write
    cannot do its work there.

A context with no producer at all is a finding too: it can never report,
on any pull request.

Selector (§G6): the set of contexts is read from the branch-protection
declaration, not from a list of workflow names, so a context added to
`settings.yml` is covered without anyone opting it in. A context
`<caller-job-id> / <reusable-job-name>` is produced by a caller job with that
id; when the caller job uses a reusable workflow by local path, the reusable
must also carry a job with that display name, otherwise renaming the reusable
job would orphan the context silently. A context without ` / ` is produced by
a plain job whose `name:` (or id, when it has no name) equals it.

Not covered: contexts that live only in a ruleset or were set through the
branch-protection UI (the Probot Settings App doesn't sync them, #369), and
contexts reported by external apps rather than workflows. Neither is in
`settings.yml`, so neither is in reach of a file-based check.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from pathlib import Path

import yaml

SEPARATOR = " / "

# Without `opened` the check does not run when the pull request is created;
# without `synchronize` it does not rerun on a new head commit, and a strict
# protection then waits for a context on a SHA nothing will ever report on.
REQUIRED_TYPES = ("opened", "synchronize")


def finding(context: str, kind: str, message: str) -> dict:
    return {"context": context, "kind": kind, "message": message}


def load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def triggers(workflow: dict) -> dict:
    """The `on:` block as a mapping of event name to its configuration.

    PyYAML implements YAML 1.1, where a bare `on` is the boolean True -- so the
    key is looked up both ways. GitHub accepts a single event as a string, a
    list of events, or a mapping; all three normalise to a mapping here.
    """
    raw = workflow.get("on", workflow.get(True))
    if isinstance(raw, str):
        return {raw: None}
    if isinstance(raw, list):
        return {str(event): None for event in raw}
    if isinstance(raw, dict):
        return {str(event): config for event, config in raw.items()}
    return {}


def is_reusable_only(workflow: dict) -> bool:
    """True when `workflow_call` is the only trigger; such a file reports nothing itself."""
    events = triggers(workflow)
    return set(events) == {"workflow_call"}


def required_contexts(settings: dict) -> list[tuple[str, str]]:
    """Every (branch, context) pair the protection declaration requires."""
    out = []
    for branch in settings.get("branches") or []:
        if not isinstance(branch, dict):
            continue
        protection = branch.get("protection") or {}
        checks = protection.get("required_status_checks") or {}
        for context in checks.get("contexts") or []:
            out.append((str(branch.get("name", "")), str(context)))
    return out


def job_display_names(workflow: dict) -> set[str]:
    return {
        str(job.get("name", job_id))
        for job_id, job in (workflow.get("jobs") or {}).items()
        if isinstance(job, dict)
    }


def produces(root: Path, job_id: str, job: dict, context: str) -> bool:
    """Whether this caller job reports the given context."""
    if SEPARATOR not in context:
        return "uses" not in job and str(job.get("name", job_id)) == context
    caller_id, reusable_name = context.split(SEPARATOR, 1)
    if job_id != caller_id or "uses" not in job:
        return False
    uses = str(job["uses"])
    if not uses.startswith("./"):
        # A remote reusable can't be read from here; the job id is all there is.
        return True
    called = root / uses[2:].split("@", 1)[0]
    if not called.is_file():
        return False
    return reusable_name in job_display_names(load_yaml(called))


def producers(root: Path, context: str) -> list[tuple[Path, dict, str, dict]]:
    """(workflow path, workflow, job id, job) for every job that reports `context`."""
    out = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        workflow = load_yaml(path)
        if is_reusable_only(workflow):
            continue
        for job_id, job in (workflow.get("jobs") or {}).items():
            if isinstance(job, dict) and produces(root, str(job_id), job, context):
                out.append((path, workflow, str(job_id), job))
    return out


def as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def check_trigger(branch: str, events: dict) -> list[str]:
    """Problems with the `pull_request` trigger; empty when it reports on every fork PR."""
    if "pull_request" not in events:
        if "pull_request_target" in events:
            return ["triggers on `pull_request_target` only, which runs the base ref "
                    "and doesn't test the pull request; it needs `pull_request`"]
        listed = ", ".join(f"`{e}`" for e in events) or "nothing"
        return [f"doesn't trigger on `pull_request` (triggers: {listed}), so a fork "
                "pull request never gets this context"]

    config = events["pull_request"] or {}
    if not isinstance(config, dict):
        return []
    problems = []
    for key in ("paths", "paths-ignore"):
        if key in config:
            problems.append(f"filters `pull_request` by `{key}`, so the context goes "
                            "unreported on pull requests outside it")
    included = as_list(config.get("branches"))
    if included and not any(fnmatch.fnmatchcase(branch, p) for p in included):
        problems.append(f"filters `pull_request` by `branches` that exclude `{branch}`")
    excluded = as_list(config.get("branches-ignore"))
    if any(fnmatch.fnmatchcase(branch, p) for p in excluded):
        problems.append(f"filters `pull_request` by `branches-ignore` that matches `{branch}`")
    types = as_list(config.get("types"))
    if types:
        missing = [t for t in REQUIRED_TYPES if t not in types]
        if missing:
            problems.append("restricts `pull_request` `types` without "
                            + ", ".join(f"`{t}`" for t in missing))
    return problems


def write_scopes(permissions) -> list[str]:
    """Scopes granted `write`; `write-all` counts as all of them."""
    if isinstance(permissions, str):
        return ["write-all"] if permissions == "write-all" else []
    if isinstance(permissions, dict):
        return sorted(str(k) for k, v in permissions.items() if str(v) == "write")
    return []


def audit(root: Path) -> list[dict]:
    settings_path = root / ".github" / "settings.yml"
    if not settings_path.is_file():
        return []
    out = []
    for branch, context in required_contexts(load_yaml(settings_path)):
        found = producers(root, context)
        if not found:
            out.append(finding(context, "no-producer",
                               f"`{branch}` requires it but no workflow under "
                               ".github/workflows/ produces it, so it can never report"))
            continue
        for path, workflow, job_id, job in found:
            name = path.relative_to(root)
            for problem in check_trigger(branch, triggers(workflow)):
                out.append(finding(context, "trigger", f"`{name}` {problem}"))
            granted = job.get("permissions", workflow.get("permissions"))
            scopes = write_scopes(granted)
            if scopes:
                out.append(finding(
                    context, "write-permission",
                    f"`{name}` job `{job_id}` grants {', '.join(f'`{s}`' for s in scopes)}; "
                    "a fork pull request's token is read-only",
                ))
    return out


def render(findings: list[dict]) -> str:
    lines = ["# Required-check triggers", ""]
    if not findings:
        lines.append("No findings. Every required context is produced by a workflow "
                     "that runs, read-only, on fork pull requests.")
        return "\n".join(lines)
    lines.append(f"**{len(findings)} finding(s).**")
    lines.append("")
    for item in findings:
        lines.append(f"- **{item['context']}** ({item['kind']}) — {item['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=".", help="repository root to check")
    args = parser.parse_args(argv)

    findings = audit(Path(args.root))
    report = render(findings)
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    if findings:
        print(f"::error::{len(findings)} required-check trigger finding(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
