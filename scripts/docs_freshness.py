#!/usr/bin/env python3
"""Audit the documentation tree for freshness.

`mkdocs build --strict` already fails on broken internal links and missing nav
entries, and it runs on every pull request. This script covers the drift it
cannot see -- the kind where every page builds and every link resolves, and the
documentation is still wrong:

  * a page added in one language only, so the other language silently lags
  * a mention of a reusable workflow that no longer exists under that name
  * a reusable workflow nobody documented, in a repository whose product IS
    its reusable workflows
  * an ADR whose prose says one status and whose index row says another
  * a placeholder somebody meant to come back to

Reads only. Exits non-zero when a critical finding is present, so a scheduled
or pre-release run cannot pass silently -- see issue #429.

Severity is deliberate rather than uniform. A parity gap, a dead reference or
an ADR contradiction states something false to a reader, and blocks. An
undocumented workflow or a placeholder is a gap rather than a falsehood: it is
reported, and only blocks under --strict. The call site picks, the way
`branch_protection_audit.py` leaves that choice to its caller.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

CRITICAL = "critical"
WARNING = "warning"

# Markers that mean "unfinished", as opposed to prose that happens to contain
# the word. Anchored to a word boundary so "todo list" in a sentence is safe.
PLACEHOLDER = re.compile(r"\b(TODO|FIXME|TBD|XXX)\b|<!--\s*placeholder", re.IGNORECASE)

# `reusable-<name>.yaml` or `.yml`, wherever it appears -- prose, a code fence
# or a table cell. The workflows are the product, so a mention is a promise.
WORKFLOW_REF = re.compile(r"reusable-[a-z0-9-]+\.ya?ml")

# `**Status:** Accepted (2026-08-01) · ...` -- the first word after the label.
ADR_STATUS = re.compile(r"^\*\*Status:\*\*\s+(\S+)", re.MULTILINE)

# `| [ADR-001](adr-001-....md) | Title | Accepted |`
ADR_ROW = re.compile(r"^\|\s*\[(ADR-\d+)\]\(([^)]+)\)\s*\|[^|]*\|\s*([^|]+?)\s*\|", re.MULTILINE)


def finding(severity: str, dimension: str, message: str) -> dict:
    return {"severity": severity, "dimension": dimension, "message": message}


def languages(docs: Path) -> list[str]:
    """Language subtrees, by directory name. Empty when docs/ has no subtrees."""
    return sorted(p.name for p in docs.iterdir() if p.is_dir() and len(p.name) == 2)


def check_parity(docs: Path, langs: list[str]) -> list[dict]:
    """Every page exists in every language, by relative path.

    A page present in one language only still builds and still links, so
    nothing else in the pipeline notices.
    """
    if len(langs) < 2:
        return []
    pages = {
        lang: {str(p.relative_to(docs / lang)) for p in (docs / lang).rglob("*.md")}
        for lang in langs
    }
    union = set().union(*pages.values())
    out = []
    for path in sorted(union):
        missing = [lang for lang in langs if path not in pages[lang]]
        if missing:
            present = [lang for lang in langs if path in pages[lang]]
            out.append(finding(
                CRITICAL, "parity",
                f"`{path}` exists in {', '.join(present)} but not in {', '.join(missing)}",
            ))
    return out


def check_workflow_refs(docs: Path, workflows: Path, extra: list[Path]) -> list[dict]:
    """Mentioned workflows exist, and existing workflows are mentioned.

    Both directions matter and they fail differently. A mention of something
    gone is a falsehood a reader can act on; a workflow nobody documented is a
    gap. Hence one critical, one warning.
    """
    if not workflows.is_dir():
        return []
    existing = {p.name for p in workflows.glob("reusable-*.y*ml")}
    if not existing:
        return []

    mentioned: dict[str, set[str]] = {}
    sources = list(docs.rglob("*.md")) + [p for p in extra if p.is_file()]
    for page in sources:
        for name in WORKFLOW_REF.findall(page.read_text(encoding="utf-8")):
            mentioned.setdefault(name, set()).add(str(page))

    out = []
    for name in sorted(set(mentioned) - existing):
        where = ", ".join(f"`{p}`" for p in sorted(mentioned[name])[:3])
        out.append(finding(
            CRITICAL, "stale-reference",
            f"`{name}` is referenced in {where} but no such workflow exists",
        ))
    for name in sorted(existing - set(mentioned)):
        out.append(finding(
            WARNING, "undocumented-workflow",
            f"`{name}` exists but no page or README mentions it",
        ))
    return out


def check_adrs(docs: Path, langs: list[str]) -> list[dict]:
    """The decision index agrees with the records it lists.

    Three ways this drifts: a record revised in prose while the index still
    says Accepted, a record that never reached the index, and an index row
    pointing at a file that is gone. The status comparison is per language,
    because the status words are translated along with everything else.
    """
    out = []
    for lang in langs:
        decisions = docs / lang / "decisions"
        index = decisions / "index.md"
        if not index.is_file():
            continue

        rows = {
            m.group(1): (m.group(2), m.group(3).strip())
            for m in ADR_ROW.finditer(index.read_text(encoding="utf-8"))
        }
        records = sorted(decisions.glob("adr-*.md"))

        listed_files = set()
        for adr_id, (target, index_status) in rows.items():
            path = decisions / target
            listed_files.add(path.name)
            if not path.is_file():
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    f"{lang}: the index lists `{target}` for {adr_id}, which does not exist",
                ))
                continue
            match = ADR_STATUS.search(path.read_text(encoding="utf-8"))
            if match is None:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    f"{lang}: `{target}` carries no `**Status:**` line",
                ))
            elif match.group(1) != index_status:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    f"{lang}: {adr_id} reads `{match.group(1)}` in the record and "
                    f"`{index_status}` in the index",
                ))

        for record in records:
            if record.name not in listed_files:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    f"{lang}: `{record.name}` exists but the decision index omits it",
                ))
    return out


def check_placeholders(docs: Path) -> list[dict]:
    """Unfinished markers left behind.

    A warning: it says the page is incomplete, which is honest, rather than
    saying something untrue.
    """
    out = []
    for page in sorted(docs.rglob("*.md")):
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if PLACEHOLDER.search(line):
                out.append(finding(
                    WARNING, "placeholder",
                    f"`{page}:{number}` carries an unfinished marker: {line.strip()[:70]}",
                ))
    return out


def audit(root: Path) -> list[dict]:
    docs = root / "docs"
    if not docs.is_dir():
        return [finding(WARNING, "setup", "no `docs/` directory; nothing to audit")]
    langs = languages(docs)
    extra = [root / "README.md"]
    return (
        check_parity(docs, langs)
        + check_workflow_refs(docs, root / ".github" / "workflows", extra)
        + check_adrs(docs, langs)
        + check_placeholders(docs)
    )


def render(findings: list[dict]) -> str:
    lines = ["# Documentation freshness", ""]
    criticals = [f for f in findings if f["severity"] == CRITICAL]
    warnings = [f for f in findings if f["severity"] == WARNING]

    if not findings:
        lines.append("No findings. Parity, workflow references, the decision index "
                     "and placeholder markers all check out.")
        return "\n".join(lines)

    lines.append(f"**{len(criticals)} critical**, {len(warnings)} warning.")
    lines.append("")
    for severity, group in ((CRITICAL, criticals), (WARNING, warnings)):
        if not group:
            continue
        lines.append(f"## {severity.capitalize()}")
        lines.append("")
        for item in group:
            lines.append(f"- **{item['dimension']}** — {item['message']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root to audit")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as blocking too; for a release gate that wants no gaps",
    )
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="report without failing; for an initial survey, not for a gate",
    )
    args = parser.parse_args(argv)

    findings = audit(Path(args.root))
    report = render(findings)
    print(report)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    blocking = [
        f for f in findings
        if f["severity"] == CRITICAL or (args.strict and f["severity"] == WARNING)
    ]
    if blocking and not args.exit_zero:
        print(
            f"::error::{len(blocking)} blocking documentation-freshness finding(s)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
