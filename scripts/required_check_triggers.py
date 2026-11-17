#!/usr/bin/env python3
"""Refuse required status contexts that a fork pull request can never satisfy.

A required context on a protected branch is reported by whichever workflow
runs the job behind it. If that workflow does not run for a fork pull request,
the context never reports there and the pull request stays BLOCKED -- no
error, no failed check, just a merge button that never turns green. Issue #462
was exactly that: `static / Static CI Tests` came from a workflow triggered on
`push` only, and a fork never pushes to this repository.

Fixing that one workflow fixes one site. This script refuses the class.

Predicate (spec/project/defect-class-guards §G3): for EVERY context the
repository requires on any branch -- `branches[*].protection.
required_status_checks.contexts` in `.github/settings.yml`, merged by branch
`name` with `.github/commons-settings.yml` when the settings `_extends` them --
at least one non-reusable workflow under `.github/workflows/` produces it, and
every job that produces it

  * runs in a workflow triggered on `pull_request` -- `pull_request_target`
    does not count: it runs the base ref by default, so the check would go
    green without testing the pull request at all;
  * isn't narrowed out of reporting: no `paths` or `paths-ignore` filter, no
    `branches` / `branches-ignore` filter that excludes the protected branch
    (GitHub filter-pattern semantics, last matching pattern wins), and, where
    `types` is given, both `opened` and `synchronize` among them;
  * carries no job-level `if:` -- a job skipped on a pull request reports
    `skipped`, and a skipped job satisfies a required check without having run;
  * grants no `write` scope -- the job's own `permissions:` block, or the
    workflow-level one when the job has none. A fork pull request's token is
    read-only, so a producer that needs write cannot do its work there;
  * declares permissions at all, on the job or the workflow. Without either,
    the token falls back to the repository default, which may be read/write,
    and the same producer then behaves differently per repository setting.

A context with no producer at all is a finding too: it can never report,
on any pull request.

One exception, by name: a context in STATUS_PRODUCERS (#465) is a commit
status, posted by a guard that must run the default branch's definition
precisely so that a fork can't rewrite it. Its workflow is held to the mirror
rule instead -- it triggers on `pull_request_target` and NOT on `pull_request`
(where the fork's own copy would run), with the same filter rules; no job of
it, nor of a reusable it calls by local path, has an `actions/checkout` step,
so no pull request code runs with the base repository's token; a step in it
posts the status (`/statuses/` and `context=<name>` in one `run:`); its jobs
carry no `if:` and declare permissions; and the only `write` scope they may
hold is `statuses`, the one that posts the verdict. A fork can't hold that
scope, which is why the verdict is a status: a check run of the same name is
something a fork's own workflow can report too.

Selector (§G6): the set of contexts is read from the branch-protection
declaration, not from a list of workflow names, so a context added to
`settings.yml` is covered without anyone opting it in. A context
`<caller-job-id> / <reusable-job-name>` is produced by a caller job with that
id; when the caller job uses a reusable workflow by local path, the reusable
must also carry a job with that display name, otherwise renaming the reusable
job would orphan the context silently. A context without ` / ` is produced by
a plain job whose `name:` (or id, when it has no name) equals it. A name part
`<name> (<values>)` is a matrix leg and matches a job named `<name>` that has
`strategy.matrix`; a job `name:` containing `${{` matches by its literal
prefix up to the expression.

Not covered: contexts that live only in a ruleset or were set through the
branch-protection UI without being declared here, and contexts reported by
external apps rather than
workflows. Neither is in the settings files, so neither is in reach of a
file-based check.

Reads only. Exits non-zero on any finding.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
from pathlib import Path

import yaml

SEPARATOR = " / "

# Without `opened` the check does not run when the pull request is created;
# without `synchronize` it does not rerun on a new head commit, and a strict
# protection then waits for a context on a SHA nothing will ever report on.
REQUIRED_TYPES = ("opened", "synchronize")

# Required contexts reported as a commit status from `pull_request_target`,
# mapped to the workflow (relative to the repository root) that posts them.
# Named one by one rather than inferred from their shape: any
# `pull_request_target` job without a checkout would otherwise pass, including
# one that checks nothing. A listed workflow is still refused if it also
# triggers on `pull_request`, checks out code, or holds any write scope but
# `statuses`.
STATUS_PRODUCERS = {
    # Fails a fork pull request that changes what the required checks run
    # (#465); under `pull_request` the fork would run its own copy of it.
    "fork-guard": ".github/workflows/fork-guard.yaml",
}

# The one write scope a STATUS_PRODUCERS workflow needs.
STATUS_SCOPE = "statuses"

CHECKOUT_ACTION = "actions/checkout"

# `Python Coverage (3.14, ubuntu-latest)` -- the name GitHub gives a matrix leg.
MATRIX_LEG = re.compile(r"^(.*) \((.*)\)$")

# The merge of settings.yml over the commons is branch_protection_audit.py's
# job; it is loaded from beside this file rather than reimplemented, so the two
# scripts cannot disagree about what a repository declares.
_AUDIT_PATH = Path(__file__).resolve().parent / "branch_protection_audit.py"
_audit_spec = importlib.util.spec_from_file_location("branch_protection_audit", _AUDIT_PATH)
branch_protection_audit = importlib.util.module_from_spec(_audit_spec)
assert _audit_spec.loader is not None
_audit_spec.loader.exec_module(branch_protection_audit)


def finding(context: str, kind: str, source: str, message: str) -> dict:
    return {"context": context, "kind": kind, "source": source, "message": message}


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
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
    return set(triggers(workflow)) == {"workflow_call"}


def required_contexts(settings: dict, commons: dict) -> list[tuple[str, str]]:
    """Every (branch, context) pair the repository requires.

    Branch names come from both files, because a branch the commons protect is
    protected in the repository too when the settings extend them; the merge
    for each branch is delegated to `branch_protection_audit.declared_contexts`.
    """
    names: list[str] = []
    docs = [settings] + ([commons] if settings.get("_extends") else [])
    for doc in docs:
        for entry in doc.get("branches") or []:
            if isinstance(entry, dict) and entry.get("name") and entry["name"] not in names:
                names.append(str(entry["name"]))
    out = []
    for branch in names:
        for context in branch_protection_audit.declared_contexts(settings, commons, branch):
            out.append((branch, str(context)))
    return out


def name_matches(job_id: str, job: dict, wanted: str) -> bool:
    """Whether a job reports under the display name `wanted`."""
    display = str(job.get("name", job_id))
    if "${{" in display:
        # The name is computed at run time; only its literal prefix is knowable.
        prefix = display.split("${{", 1)[0]
        if prefix:
            return wanted.startswith(prefix)
        # A name that STARTS with an expression has no literal prefix, and ""
        # is a prefix of every context -- the job would "produce" all of them
        # and hide a real orphan. Fall back to the job id instead: wrong in the
        # loud direction (a context this job really reports may come out as
        # no-producer, which a reader can see and fix by giving the name a
        # literal prefix), never in the silent one.
        return wanted == job_id
    if display == wanted:
        return True
    leg = MATRIX_LEG.match(wanted)
    has_matrix = isinstance(job.get("strategy"), dict) and "matrix" in job["strategy"]
    return bool(leg and has_matrix and leg.group(1) in (display, job_id))


def produces(root: Path, job_id: str, job: dict, context: str) -> bool:
    """Whether this caller job reports the given context."""
    if SEPARATOR not in context:
        return "uses" not in job and name_matches(job_id, job, context)
    caller_id, reusable_name = context.split(SEPARATOR, 1)
    if job_id != caller_id or "uses" not in job:
        return False
    uses = str(job["uses"])
    if not uses.startswith("./"):
        # A remote reusable can't be read from here; the job id is all there is.
        return True
    called = load_yaml(root / uses[2:].split("@", 1)[0])
    return any(
        isinstance(rjob, dict) and name_matches(str(rid), rjob, reusable_name)
        for rid, rjob in (called.get("jobs") or {}).items()
    )


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


def pattern_regex(pattern: str) -> re.Pattern:
    """Translate a GitHub filter pattern into a regular expression.

    `*` matches anything but `/`, `**` matches anything, `?` and `+` quantify
    the preceding character (zero-or-one, one-or-more), `[...]` is a character
    class and `\\` escapes the next character -- the GitHub filter-pattern
    cheat sheet, rather than shell globbing, where `*` would cross `/`.

    Never raises. A `?` or `+` with no preceding character to quantify -- at
    the start, or after a wildcard or another quantifier -- is taken literally,
    and anything `re` still rejects (a reversed range in `[...]`, say) yields a
    pattern that matches nothing. One malformed filter must not crash the audit
    of every other context.
    """
    out, i = [], 0
    # Whether the last emitted token is a single atom `?` / `+` may quantify.
    quantifiable = False
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            quantifiable = False
            i += 2
            continue
        if char == "*":
            out.append("[^/]*")
            quantifiable = False
        elif char in "?+":
            out.append(char if quantifiable else re.escape(char))
            quantifiable = not quantifiable
        elif char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(re.escape(char))
                quantifiable = True
            else:
                out.append(pattern[i:end + 1])
                quantifiable = True
                i = end + 1
                continue
        elif char == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            quantifiable = True
            i += 2
            continue
        else:
            out.append(re.escape(char))
            quantifiable = True
        i += 1
    try:
        return re.compile("".join(out))
    except re.error:
        return re.compile(r"(?!)")


def branch_selected(branch: str, patterns: list[str]) -> bool:
    """Whether `patterns` select `branch`; a leading `!` negates, the last match wins."""
    selected = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        if pattern_regex(pattern[1:] if negated else pattern).fullmatch(branch):
            selected = not negated
    return selected


def check_trigger(branch: str, events: dict) -> list[str]:
    """Problems with the `pull_request` trigger; empty when it reports on every fork PR."""
    if "pull_request" not in events:
        if "pull_request_target" in events:
            return ["triggers on `pull_request_target` only, which runs the base ref "
                    "and doesn't test the pull request; it needs `pull_request`"]
        listed = ", ".join(f"`{e}`" for e in events) or "nothing"
        return [f"doesn't trigger on `pull_request` (triggers: {listed}), so a fork "
                "pull request never gets this context"]
    return check_filters(branch, "pull_request", events["pull_request"])


def check_base_ref_trigger(branch: str, events: dict) -> list[str]:
    """Problems with a STATUS_PRODUCERS workflow's trigger (#465)."""
    problems = []
    if "pull_request" in events:
        problems.append("posts a guard status but also triggers on `pull_request`, "
                        "where a fork runs its own copy of it")
    if "pull_request_target" not in events:
        listed = ", ".join(f"`{e}`" for e in events) or "nothing"
        problems.append(f"posts a guard status but doesn't trigger on "
                        f"`pull_request_target` (triggers: {listed})")
        return problems
    return problems + check_filters(branch, "pull_request_target",
                                    events["pull_request_target"])


def check_filters(branch: str, event: str, config) -> list[str]:
    """Filters on `event` that keep the context from reporting on some pull request."""
    config = config or {}
    if not isinstance(config, dict):
        return []
    problems = []
    for key in ("paths", "paths-ignore"):
        if key in config:
            problems.append(f"filters `{event}` by `{key}`, so the context goes "
                            "unreported on pull requests outside it")
    if "branches" in config and not branch_selected(branch, as_list(config["branches"])):
        problems.append(f"filters `{event}` by `branches` that exclude `{branch}`")
    if branch_selected(branch, as_list(config.get("branches-ignore"))):
        problems.append(f"filters `{event}` by `branches-ignore` that matches `{branch}`")
    types = as_list(config.get("types"))
    if types:
        missing = [t for t in REQUIRED_TYPES if t not in types]
        if missing:
            problems.append(f"restricts `{event}` `types` without "
                            + ", ".join(f"`{t}`" for t in missing))
    return problems


def checkout_steps(root: Path, workflow: dict) -> list[str]:
    """Where a job checks out code: "job `<id>`", prefixed by the reusable's path.

    Covers every job of the workflow, not only the one producing the context --
    all of them run under the same trigger with the same token -- and every
    reusable they call by local path, since under `pull_request_target` a local
    path resolves on the default branch and is part of what runs.
    """
    out = []
    for where, job_id, job in job_tree(root, workflow):
        for step in job.get("steps") or []:
            uses = str(step.get("uses", "")) if isinstance(step, dict) else ""
            if uses.split("@", 1)[0] == CHECKOUT_ACTION:
                out.append(f"{where}job `{job_id}`")
                break
    return out


def job_tree(root: Path, workflow: dict, seen: frozenset[str] = frozenset()):
    """(prefix, job id, job) for every job of the workflow and of the reusables
    it calls by local path; `seen` stops a reusable that calls itself."""
    for job_id, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        yield "", str(job_id), job
        uses = str(job.get("uses", ""))
        if uses.startswith("./"):
            called = uses[2:].split("@", 1)[0]
            if called in seen:
                continue
            for where, inner_id, inner in job_tree(root, load_yaml(root / called),
                                                   seen | {called}):
                yield f"`{called}` {where}", inner_id, inner


def posts_status(root: Path, workflow: dict, context: str) -> bool:
    """Whether a `run:` step in the job tree posts the commit status `context`."""
    marker = re.compile(r"context=[\"']?" + re.escape(context) + r"[\"']?(\s|$)")
    for _, _, job in job_tree(root, workflow):
        for step in job.get("steps") or []:
            run = str(step.get("run", "")) if isinstance(step, dict) else ""
            if "/statuses/" in run and marker.search(run):
                return True
    return False


def write_scopes(permissions) -> list[str]:
    """Scopes granted `write`; `write-all` counts as all of them."""
    if isinstance(permissions, str):
        return ["write-all"] if permissions == "write-all" else []
    if isinstance(permissions, dict):
        return sorted(str(k) for k, v in permissions.items() if str(v) == "write")
    return []


def check_job(name: str, workflow: dict, job_id: str, job: dict,
              allowed_writes: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    """(kind, message) problems with the producing job itself."""
    out = []
    if "if" in job:
        out.append(("job-condition",
                    f"`{name}` job `{job_id}` runs only `if: {job['if']}`; a skipped job "
                    "satisfies a required check without having run"))
    if "permissions" not in job and "permissions" not in workflow:
        out.append(("no-permissions",
                    f"`{name}` declares no `permissions:` on job `{job_id}` or the "
                    "workflow, so the token falls back to the repository default"))
    scopes = [s for s in write_scopes(job.get("permissions", workflow.get("permissions")))
              if s not in allowed_writes]
    if scopes:
        out.append(("write-permission",
                    f"`{name}` job `{job_id}` grants {', '.join(f'`{s}`' for s in scopes)}; "
                    "a fork pull request's token is read-only"))
    return out


def audit_status_producer(root: Path, branch: str, context: str, add) -> None:
    """Hold a STATUS_PRODUCERS workflow to the mirror rule (#465)."""
    name = STATUS_PRODUCERS[context]
    workflow = load_yaml(root / name)
    if not workflow:
        add(context, "", "no-producer",
            f"required commit status, but `{name}`, which should post it, doesn't exist")
        return
    if not posts_status(root, workflow, context):
        add(context, name, "no-producer",
            f"`{name}` should post this commit status, but no `run:` step in it or a "
            f"reusable it calls by local path does (`/statuses/` and `context={context}`)")
    for problem in check_base_ref_trigger(branch, triggers(workflow)):
        add(context, name, "trigger", f"`{name}` {problem}")
    for where in checkout_steps(root, workflow):
        add(context, name, "checkout",
            f"`{name}` runs under `pull_request_target`, and {where} checks out "
            "code: never run pull request code with the base repository's token")
    for job_id, job in (workflow.get("jobs") or {}).items():
        if isinstance(job, dict):
            for kind, message in check_job(name, workflow, str(job_id), job,
                                           frozenset({STATUS_SCOPE})):
                add(context, name, kind, message)


def audit(root: Path) -> list[dict]:
    settings = load_yaml(root / ".github" / "settings.yml")
    # The commons are read from this checkout. In the repository that ships
    # them that is the copy `_extends` resolves to; in a consumer the file is
    # absent and only the consumer's own declaration is checked.
    commons = load_yaml(root / branch_protection_audit.COMMONS_PATH)

    # One finding per (context, file, kind): a context required on several
    # branches is one defect, not one per branch. Distinct problems of the same
    # kind -- a `paths` filter and a `types` filter -- are joined, not dropped.
    found: dict[tuple[str, str, str], list[str]] = {}

    def add(context: str, source: str, kind: str, message: str) -> None:
        messages = found.setdefault((context, source, kind), [])
        if message not in messages:
            messages.append(message)

    for branch, context in required_contexts(settings, commons):
        if context in STATUS_PRODUCERS:
            audit_status_producer(root, branch, context, add)
            continue
        jobs = producers(root, context)
        if not jobs:
            add(context, "", "no-producer",
                "required but no workflow under .github/workflows/ produces it, "
                "so it can never report")
            continue
        for path, workflow, job_id, job in jobs:
            name = path.relative_to(root).as_posix()
            for problem in check_trigger(branch, triggers(workflow)):
                add(context, name, "trigger", f"`{name}` {problem}")
            for kind, message in check_job(name, workflow, job_id, job):
                add(context, name, kind, message)

    return [
        finding(context, kind, source, "; ".join(messages))
        for (context, source, kind), messages in found.items()
    ]


def render(findings: list[dict]) -> str:
    lines = ["# Required-check triggers", ""]
    if not findings:
        lines.append("No findings. Every required context is produced by a workflow "
                     "that reports it on fork pull requests, read-only or as a guard status.")
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
