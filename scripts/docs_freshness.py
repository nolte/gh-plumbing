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


# The step summary is Markdown that GitHub renders (#506). File names, ADR
# targets, status words and doc lines are repository content, so the summary
# writes each one encoded, then wrapped: control characters become '?', ASCII
# punctuation a numeric HTML entity, inside <code> (md_code) or <pre> (md_pre).
# The same helpers as scripts/workflow_command_masking.py's PY_MD, which a
# test holds this copy to.
def md_enc(value):
    return re.sub(r"[\x21-\x2f\x3a-\x40\x5b-\x60\x7b-\x7e]", lambda m: f"&#{ord(m.group())};",
                  re.sub(r"[\x00-\x1f\x7f-\x9f]", "?", str(value)))


def md_code(value):
    return f"<code>{md_enc(value)}</code>"


def md_pre(value):
    lines = str(value).replace("\r\n", "\n").split("\n")
    return "<pre>" + "\n".join(md_enc(line) for line in lines) + "\n</pre>"


def phrase(template: str, *values) -> tuple[str, str]:
    """A sentence as plain text and as step-summary Markdown.

    Each `{}` takes one value, or a list of values. In the plain text a slot
    written as `` `{}` `` is a code span (a list: one span per item); in the
    Markdown every value is md_code() instead, and the slot's backticks go.
    """
    pieces = template.split("{}")
    assert len(pieces) == len(values) + 1, template
    plain, markdown = pieces[0], pieces[0]
    for i, value in enumerate(values):
        items = [str(v) for v in value] if isinstance(value, (list, tuple)) else [str(value)]
        quoted = pieces[i].endswith("`") and pieces[i + 1].startswith("`")
        plain += ("`, `" if quoted else ", ").join(items) + pieces[i + 1]
        markdown = (markdown[:-1] if quoted else markdown) + ", ".join(md_code(v) for v in items) \
            + (pieces[i + 1][1:] if quoted else pieces[i + 1])
    return plain, markdown


def finding(severity: str, dimension: str, template: str, *values) -> dict:
    """`message` is the plain sentence, `markdown` the same for the step summary."""
    message, markdown = phrase(template, *values)
    return {"severity": severity, "dimension": dimension, "message": message, "markdown": markdown}


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
                "`{}` exists in {} but not in {}", path, present, missing,
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
        out.append(finding(
            CRITICAL, "stale-reference",
            "`{}` is referenced in `{}` but no such workflow exists", name, sorted(mentioned[name])[:3],
        ))
    for name in sorted(existing - set(mentioned)):
        out.append(finding(
            WARNING, "undocumented-workflow",
            "`{}` exists but no page or README mentions it", name,
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
                    "{}: the index lists `{}` for {}, which does not exist", lang, target, adr_id,
                ))
                continue
            match = ADR_STATUS.search(path.read_text(encoding="utf-8"))
            if match is None:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    "{}: `{}` carries no `**Status:**` line", lang, target,
                ))
            elif match.group(1) != index_status:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    "{}: {} reads `{}` in the record and `{}` in the index",
                    lang, adr_id, match.group(1), index_status,
                ))

        for record in records:
            if record.name not in listed_files:
                out.append(finding(
                    CRITICAL, "adr-hygiene",
                    "{}: `{}` exists but the decision index omits it", lang, record.name,
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
                    "`{}` carries an unfinished marker: {}", f"{page}:{number}", line.strip()[:70],
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


def render(findings: list[dict], markdown: bool = True) -> str:
    """The report: for the step summary (`markdown`), or as plain text for the log."""
    key = "markdown" if markdown else "message"
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
            lines.append(f"- **{item['dimension']}** — {item[key]}")
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
    print(render(findings, markdown=False))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(render(findings) + "\n")

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
