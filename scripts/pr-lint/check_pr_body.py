#!/usr/bin/env python3
"""Lint a pull request's title and body against spec/project/pull-request-workflow/.

The spec lives in nolte/claude-shared; every `spec/...` path below refers to that corpus.
Guard origin (spec/project/defect-class-guards/ G5): claude-shared#574 (class sweep),
claude-shared#577 (the check itself, moved here) and claude-shared#616 (traceability).
Run by .github/workflows/reusable-pr-lint.yaml.

Implements the checks that spec §"PR lint workflow" declares as a required status
check: the Conventional-Commits title form, the five required body sections in
order, the non-empty rule for Summary / Changes / Testing, and the
type-conditional `## Class sweep` section that §"Class sweep (Conventional-Commits
type `fix`)" requires on type `fix` and forbids on every other type.

A pull request whose author login is on EXEMPT_BOT_AUTHORS gets the title check
only. A dependency bot writes its body from a fixed template that can't carry the
reasoning the five sections exist for, so holding it to them would only ever
produce filler (spec §PR preconditions).

Reads the title, body and author from the environment (PR_TITLE / PR_BODY /
PR_AUTHOR) or from --title / --body-file / --author, so a workflow never
interpolates untrusted pull-request text into a shell command. Without an author
the pull request is treated as human-authored, which exempts nothing.

Exit code 0 when every rule holds, 1 when any fails, 2 on a usage error.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

TYPES = ("feat", "fix", "chore", "docs", "exp")
TITLE_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^()]+)\))?: (?P<summary>.+)$")

REQUIRED_SECTIONS = ("Summary", "Changes", "Linked issues", "Testing", "Risk / rollout notes")
NON_EMPTY_SECTIONS = ("Summary", "Changes", "Testing")
SWEEP_SECTION = "Class sweep"
SWEEP_FIELDS = ("Predicate", "Hits", "Repaired", "Guard")
INTEGER_FIELDS = ("Hits", "Repaired")

# Dependency bots whose pull requests skip the body checks, keyed by the author
# login GitHub puts in the event payload. Every entry needs a reason (spec §PR
# preconditions). Matching is exact, never on the account type, so an unlisted
# bot stays subject to every rule.
EXEMPT_BOT_AUTHORS: dict[str, str] = {
    "renovate[bot]": (
        "Renovate writes its own body from a fixed template: a dependency table, the "
        "upstream release notes and its rebase controls. It can't supply the human "
        "reasoning Summary and Testing exist for, so the five sections would only ever "
        "hold filler. Its title already uses Conventional Commits and is still checked."
    ),
}

HEADING_RE = re.compile(r"^##[ \t]+(?P<name>.+?)[ \t]*$", re.MULTILINE)


def split_sections(body: str) -> list[tuple[str, str]]:
    """Return [(heading, content)] for every level-2 heading, in document order."""
    matches = list(HEADING_RE.finditer(body))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        out.append((m.group("name"), body[m.end():end]))
    return out


def strip_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def is_empty(content: str) -> bool:
    stripped = strip_comments(content).strip()
    return not stripped or stripped == "None"


def field_value(content: str, field: str) -> str | None:
    """Value of a `- <Field>: <value>` line, or None when the line is absent."""
    pattern = re.compile(rf"^[-*][ \t]+{re.escape(field)}:[ \t]*(?P<value>.*)$", re.MULTILINE)
    m = pattern.search(strip_comments(content))
    if m is None:
        return None
    return m.group("value").strip()


# spec/project/spec-driven-development/ Requirement 2 (#585, revisit trigger (a) fired
# with #561 and #571): a pull request touching implementation paths names its spec.
REFS_SPEC_RE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?Refs[ \t]+`?spec/[a-z0-9-]+/[a-z0-9-]+/?", re.MULTILINE | re.IGNORECASE)


def check_spec_anchor(pr_type: str | None, linked_issues: str | None, changed_files: list[str] | None,
                      head_ref: str | None) -> list[str]:
    """Require a `Refs spec/<topic>/<slug>/` line when implementation paths change.

    Exempt: no file list (a local run), a spec-only change, and an `exp/` branch;
    dependency bots return earlier. A purely cosmetic edit names its anchor like any
    other: `Refs spec/project/prose-style/`.
    """
    if changed_files is None or (head_ref or "").startswith("exp/"):
        return []
    implementation = [f for f in changed_files if f and not f.startswith("spec/")]
    if not implementation or REFS_SPEC_RE.search(strip_comments(linked_issues or "")):
        return []
    return [
        f"the pull request changes {len(implementation)} implementation path(s) (for example "
        f"`{implementation[0]}`) but `## Linked issues` carries no `Refs spec/<topic>/<slug>/` line "
        "(spec/project/spec-driven-development/ Requirement 2; a purely cosmetic edit names `Refs spec/project/prose-style/`)"
    ]


# spec/project/continuous-improvement/ §"Traceability in remediation artifacts" (#616):
# a pull request whose `## Linked issues` references an issue carrying the audit
# label remediates an audit finding, so its Risk / rollout notes name the finding
# source and the specialist. Only issue numbers leave the checker; the workflow
# reads their labels and hands them back through a file.
AUDIT_LABEL = "audit"
LINKED_ISSUE_RE = re.compile(r"(?<![\w/])#(\d{1,9})\b")
TRACEABILITY_FIELDS = ("Originating source", "Dispatched specialist")
# Neither allowed form needs dispatch-status wording: the specialist form names
# who produced the fix, the no-match form says none existed. Reading negations
# in free text leaks in both directions, so the check rejects the vocabulary
# itself (any form, markdown ignored). A bypass worded without it isn't caught
# here; the coverage review still reads the field.
DISPATCH_STATUS_RE = re.compile(r"(?:dispatch|invo[kc]|bypass)", re.IGNORECASE)


def linked_issue_numbers(body: str, repository: str | None = None) -> list[int]:
    """Same-repository references in `## Linked issues`, in order, without duplicates.

    Reads `#N` and, when `repository` (`owner/name`) is known, full issue or pull
    request URLs of that repository, which GitHub links the same way.
    """
    content = strip_comments(dict(split_sections(body)).get("Linked issues") or "")
    found = [(m.start(), m.group(1)) for m in LINKED_ISSUE_RE.finditer(content)]
    if repository:
        url_re = re.compile(rf"github\.com/{re.escape(repository)}/(?:issues|pull)/(\d{{1,9}})\b", re.IGNORECASE)
        found += [(m.start(), m.group(1)) for m in url_re.finditer(content)]
    seen: list[int] = []
    for _, number in sorted(found):
        if int(number) not in seen:
            seen.append(int(number))
    return seen


def risk_field(content: str, field: str) -> str | None:
    """The value of `field:` in `content`, joined with its more deeply indented continuation lines."""
    lines = strip_comments(content).split("\n")
    pattern = re.compile(rf"^(?P<indent>[ \t]*)(?:[-*][ \t]+)?{re.escape(field)}:[ \t]*(?P<value>.*)$")
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        indent = len(match.group("indent").expandtabs())
        parts = [match.group("value").strip()]
        for follow in lines[i + 1:]:
            if not follow.strip():
                break
            if len(follow) - len(follow.lstrip()) <= indent:
                break
            parts.append(follow.strip())
        return " ".join(p for p in parts if p)
    return None


def check_traceability(risk: str | None, audit_issues: list[int]) -> list[str]:
    if not audit_issues:
        return []
    refs = ", ".join(f"#{n}" for n in audit_issues)
    failures: list[str] = []
    values = {field: risk_field(risk or "", field) for field in TRACEABILITY_FIELDS}
    for field, value in values.items():
        if not value or value.startswith("<"):
            failures.append(
                f"`## Linked issues` references the audit issue(s) {refs}, but `## Risk / rollout notes` "
                f"carries no `{field}:` line with a value "
                '(spec/project/continuous-improvement/ §"Traceability in remediation artifacts")'
            )
    specialist = values["Dispatched specialist"]
    plain = re.sub(r"[`*_~]", "", specialist or "")
    if DISPATCH_STATUS_RE.search(plain):
        failures.append(
            "`Dispatched specialist:` carries dispatch-status wording (dispatch, invoke, bypass), which neither "
            "allowed form needs: name the specialist that produced the fix, or write `no matching specialist "
            "existed — generalist handled`, and keep any remark about what was or wasn't dispatched out of this field "
            '(spec/project/continuous-improvement/ §"Specialist dispatch")'
        )
    return failures


def check(title: str, body: str, author: str | None = None, changed_files: list[str] | None = None,
          head_ref: str | None = None, audit_issues: list[int] | None = None,
          spec_anchor: bool = False) -> list[str]:
    failures: list[str] = []

    title_match = TITLE_RE.match(title.strip())
    if title_match is None:
        failures.append(
            f"title {title.strip()!r} does not match the Conventional Commits form "
            "`<type>(<scope>)?: <summary>` (spec §PR preconditions)"
        )
        pr_type = None
    else:
        pr_type = title_match.group("type")
        if pr_type not in TYPES:
            failures.append(
                f"title type {pr_type!r} is outside the closed vocabulary "
                f"{{{', '.join(TYPES)}}} (spec §PR preconditions)"
            )
            pr_type = None

    if author in EXEMPT_BOT_AUTHORS:
        return failures

    sections = split_sections(body)
    headings = [name for name, _ in sections]
    by_name = {name: content for name, content in sections}

    missing = [s for s in REQUIRED_SECTIONS if s not in by_name]
    if missing:
        failures.append(
            "body is missing the required section(s) "
            + ", ".join(f"`## {s}`" for s in missing)
            + " (spec §PR description structure)"
        )
    else:
        positions = [headings.index(s) for s in REQUIRED_SECTIONS]
        if positions != sorted(positions):
            failures.append(
                "the five required sections are present but out of order; expected "
                + " → ".join(REQUIRED_SECTIONS)
                + " (spec §PR description structure)"
            )

    if spec_anchor:
        failures += check_spec_anchor(pr_type, by_name.get("Linked issues"), changed_files, head_ref)
    failures += check_traceability(by_name.get("Risk / rollout notes"), audit_issues or [])

    for name in NON_EMPTY_SECTIONS:
        if name in by_name and is_empty(by_name[name]):
            failures.append(
                f"section `## {name}` is empty or contains only `None`; only "
                "Linked issues and Risk / rollout notes may be `None` "
                "(spec §PR description structure)"
            )

    if pr_type == "fix":
        if SWEEP_SECTION not in by_name:
            failures.append(
                f"a `fix` pull request must carry a `## {SWEEP_SECTION}` section stating the "
                "defect class it swept, in numbers "
                '(spec §"Class sweep (Conventional-Commits type `fix`)")'
            )
        else:
            content = by_name[SWEEP_SECTION]
            for field in SWEEP_FIELDS:
                value = field_value(content, field)
                if value is None:
                    failures.append(
                        f"`## {SWEEP_SECTION}` is missing the field `- {field}:` "
                        '(spec §"Class sweep (Conventional-Commits type `fix`)")'
                    )
                    continue
                if not value or value.startswith("<"):
                    failures.append(
                        f"`## {SWEEP_SECTION}` field `{field}` is empty or still carries its "
                        "placeholder "
                        '(spec §"Class sweep (Conventional-Commits type `fix`)")'
                    )
                    continue
                if field in INTEGER_FIELDS and not re.fullmatch(r"\d+", value):
                    failures.append(
                        f"`## {SWEEP_SECTION}` field `{field}` is {value!r}, which is not an "
                        "integer; the section states counts, not prose "
                        '(spec §"Class sweep (Conventional-Commits type `fix`)")'
                    )

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", default=None, help="PR title; defaults to $PR_TITLE")
    parser.add_argument("--body-file", default=None, help="file holding the PR body; defaults to $PR_BODY")
    parser.add_argument("--author", default=None, help="PR author login from the event payload; defaults to $PR_AUTHOR")
    parser.add_argument("--changed-files-file", default=None, help="file listing changed paths, one per line; defaults to $CHANGED_FILES_FILE (used when $SPEC_ANCHOR is true)")
    parser.add_argument("--linked-issue-labels-file", default=None, help="file of `<issue> <label>` lines; defaults to $LINKED_ISSUE_LABELS_FILE")
    parser.add_argument("--print-linked-issues", action="store_true", help="print the `## Linked issues` numbers of the body, one per line, and exit")
    args = parser.parse_args(argv)

    title = args.title if args.title is not None else os.environ.get("PR_TITLE")
    if args.body_file is not None:
        with open(args.body_file, encoding="utf-8") as handle:
            body = handle.read()
    else:
        body = os.environ.get("PR_BODY")
    author = args.author if args.author is not None else os.environ.get("PR_AUTHOR")

    if args.print_linked_issues:
        if body is None:
            print("usage: provide --body-file or set PR_BODY", file=sys.stderr)
            return 2
        for number in linked_issue_numbers(body, os.environ.get("GITHUB_REPOSITORY")):
            print(number)
        return 0

    if title is None or body is None:
        print("usage: provide --title/--body-file or set PR_TITLE/PR_BODY", file=sys.stderr)
        return 2

    files_path = args.changed_files_file or os.environ.get("CHANGED_FILES_FILE")
    changed_files = None
    if files_path:
        with open(files_path, encoding="utf-8") as handle:
            changed_files = [line.strip() for line in handle if line.strip()]
    audit_label = os.environ.get("AUDIT_LABEL", AUDIT_LABEL)
    labels_path = args.linked_issue_labels_file or os.environ.get("LINKED_ISSUE_LABELS_FILE")
    audit_issues: list[int] = []
    if labels_path:
        with open(labels_path, encoding="utf-8") as handle:
            for line in handle:
                number, _, label = line.strip().partition(" ")
                if audit_label and number.isdigit() and label == audit_label and int(number) not in audit_issues:
                    audit_issues.append(int(number))
    spec_anchor = os.environ.get("SPEC_ANCHOR", "").strip().lower() == "true"
    failures = check(title, body, author, changed_files, os.environ.get("PR_HEAD_REF"), audit_issues, spec_anchor)
    if failures:
        print(f"PR body lint: {len(failures)} failure(s)\n")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nSee spec/project/pull-request-workflow/en.md "
            '§"PR description structure" and §"PR lint workflow".'
        )
        return 1
    if author in EXEMPT_BOT_AUTHORS:
        print(f"PR body lint: pass (body checks skipped for the allowlisted dependency bot {author})")
    else:
        print("PR body lint: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
