"""Tests for scripts/docs_freshness.py.

The script exists because `mkdocs build --strict` passes on documentation that
is wrong -- every page builds, every link resolves, and a reader is still
misled. So the load-bearing cases here are the ones where a naive checker would
report nothing: a page present in one language only, a mention of a workflow
that no longer exists, an index row contradicting the record it links to.

Each test builds a documentation tree under `tmp_path`, so nothing touches the
repository's own docs and no test depends on their current state.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs_freshness.py"
_spec = importlib.util.spec_from_file_location("docs_freshness", MODULE_PATH)
freshness = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(freshness)

ADR_RECORD = """# ADR-001: Something

**Status:** {status} (2026-01-01) · **Issue:** [#1](https://example.invalid/1)

## Context

Text.
"""

ADR_INDEX = """# Decisions

| Record | Subject | Status |
|---|---|---|
| [ADR-001](adr-001-something.md) | Something | {status} |
"""


def write(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def tree(tmp_path):
    """A minimal, healthy two-language documentation tree."""
    for lang in ("en", "de"):
        write(tmp_path / "docs" / lang / "index.md", "# Home\n")
        write(tmp_path / "docs" / lang / "workflows" / "index.md", "# Workflows\n")
    write(tmp_path / ".github" / "workflows" / "reusable-thing.yaml", "name: Thing\n")
    write(tmp_path / "docs" / "en" / "workflows" / "index.md",
          "# Workflows\n\n`reusable-thing.yaml` does a thing.\n")
    write(tmp_path / "README.md", "# Repo\n")
    return tmp_path


def dimensions(findings, severity=None):
    return sorted(
        f["dimension"] for f in findings
        if severity is None or f["severity"] == severity
    )


def test_healthy_tree_reports_nothing(tree):
    """The baseline. Without it, every other assertion could pass vacuously."""
    assert freshness.audit(tree) == []


def test_page_in_one_language_only_is_critical(tree):
    """mkdocs builds this happily; the other language silently lags."""
    write(tree / "docs" / "en" / "workflows" / "solo.md", "# Solo\n")

    findings = freshness.audit(tree)

    assert dimensions(findings, freshness.CRITICAL) == ["parity"]
    assert "workflows/solo.md" in findings[0]["message"]
    assert "de" in findings[0]["message"]


def test_reference_to_a_missing_workflow_is_critical(tree):
    """A reader can act on this one, which is why it blocks."""
    write(tree / "docs" / "en" / "workflows" / "index.md",
          "# Workflows\n\n`reusable-thing.yaml` and `reusable-gone.yaml`.\n")
    write(tree / "docs" / "de" / "workflows" / "index.md", "# Workflows\n")

    findings = freshness.audit(tree)
    stale = [f for f in findings if f["dimension"] == "stale-reference"]

    assert len(stale) == 1
    assert stale[0]["severity"] == freshness.CRITICAL
    assert "reusable-gone.yaml" in stale[0]["message"]


def test_undocumented_workflow_is_only_a_warning(tree):
    """A gap, not a falsehood -- so it reports without blocking."""
    write(tree / ".github" / "workflows" / "reusable-quiet.yaml", "name: Quiet\n")

    findings = freshness.audit(tree)
    undocumented = [f for f in findings if f["dimension"] == "undocumented-workflow"]

    assert len(undocumented) == 1
    assert undocumented[0]["severity"] == freshness.WARNING
    assert "reusable-quiet.yaml" in undocumented[0]["message"]


def test_readme_counts_as_documentation(tree):
    """The catalog lives in README.md and is included into the site."""
    write(tree / ".github" / "workflows" / "reusable-listed.yaml", "name: Listed\n")
    write(tree / "README.md", "# Repo\n\n| `reusable-listed.yaml` | does things |\n")

    findings = freshness.audit(tree)

    assert not [f for f in findings if f["dimension"] == "undocumented-workflow"]


def test_status_mismatch_between_record_and_index_is_critical(tree):
    """The drift nobody sees: prose says Revised, the index still says Accepted."""
    write(tree / "docs" / "en" / "decisions" / "adr-001-something.md",
          ADR_RECORD.format(status="Revised"))
    write(tree / "docs" / "en" / "decisions" / "index.md",
          ADR_INDEX.format(status="Accepted"))
    write(tree / "docs" / "de" / "decisions" / "adr-001-something.md",
          ADR_RECORD.format(status="Accepted"))
    write(tree / "docs" / "de" / "decisions" / "index.md",
          ADR_INDEX.format(status="Accepted"))

    findings = freshness.audit(tree)
    adr = [f for f in findings if f["dimension"] == "adr-hygiene"]

    assert len(adr) == 1, "only the English pair disagrees"
    assert adr[0]["severity"] == freshness.CRITICAL
    assert "Revised" in adr[0]["message"] and "Accepted" in adr[0]["message"]


def test_status_words_are_compared_within_a_language(tree):
    """German records say `Überarbeitet` where English says `Revised`.

    Comparing across languages would report every translated record as drift,
    which is why the check is per language rather than per record id.
    """
    write(tree / "docs" / "en" / "decisions" / "adr-001-something.md",
          ADR_RECORD.format(status="Revised"))
    write(tree / "docs" / "en" / "decisions" / "index.md",
          ADR_INDEX.format(status="Revised"))
    write(tree / "docs" / "de" / "decisions" / "adr-001-something.md",
          ADR_RECORD.format(status="Überarbeitet"))
    write(tree / "docs" / "de" / "decisions" / "index.md",
          ADR_INDEX.format(status="Überarbeitet"))

    assert not [f for f in freshness.audit(tree) if f["dimension"] == "adr-hygiene"]


def test_record_missing_from_the_index_is_critical(tree):
    """A decision nobody can find from the index is undocumented in practice."""
    for lang in ("en", "de"):
        write(tree / "docs" / lang / "decisions" / "adr-001-something.md",
              ADR_RECORD.format(status="Accepted"))
        write(tree / "docs" / lang / "decisions" / "index.md",
              "# Decisions\n\n| Record | Subject | Status |\n|---|---|---|\n")

    findings = freshness.audit(tree)
    adr = [f for f in findings if f["dimension"] == "adr-hygiene"]

    assert len(adr) == 2, "one per language"
    assert all(f["severity"] == freshness.CRITICAL for f in adr)
    assert all("omits it" in f["message"] for f in adr)


def test_index_row_pointing_at_a_missing_file_is_critical(tree):
    """The inverse: the index promises a record that is gone."""
    for lang in ("en", "de"):
        write(tree / "docs" / lang / "decisions" / "index.md",
              ADR_INDEX.format(status="Accepted"))

    findings = freshness.audit(tree)
    adr = [f for f in findings if f["dimension"] == "adr-hygiene"]

    assert len(adr) == 2
    assert all("does not exist" in f["message"] for f in adr)


def test_placeholder_marker_is_a_warning(tree):
    """Honest incompleteness, so it reports without blocking."""
    write(tree / "docs" / "en" / "index.md", "# Home\n\nTODO: write this.\n")

    findings = freshness.audit(tree)
    markers = [f for f in findings if f["dimension"] == "placeholder"]

    assert len(markers) == 1
    assert markers[0]["severity"] == freshness.WARNING


def test_the_word_todo_in_prose_does_not_trip_the_marker(tree):
    """`\\b` anchoring, so a sentence about a todo list stays clean."""
    write(tree / "docs" / "en" / "index.md", "# Home\n\nThe todos are tracked in issues.\n")
    write(tree / "docs" / "de" / "index.md", "# Home\n\nThe todos are tracked in issues.\n")

    assert not [f for f in freshness.audit(tree) if f["dimension"] == "placeholder"]


def test_main_exits_non_zero_on_a_critical_finding(tree, capsys):
    write(tree / "docs" / "en" / "workflows" / "solo.md", "# Solo\n")

    assert freshness.main(["--root", str(tree)]) == 1


def test_exit_zero_reports_without_failing(tree, capsys):
    write(tree / "docs" / "en" / "workflows" / "solo.md", "# Solo\n")

    assert freshness.main(["--root", str(tree), "--exit-zero"]) == 0
    assert "parity" in capsys.readouterr().out


def test_warnings_alone_do_not_block_unless_strict(tree):
    """The choice the release gate makes, and the pull-request job does not."""
    write(tree / ".github" / "workflows" / "reusable-quiet.yaml", "name: Quiet\n")

    assert freshness.main(["--root", str(tree)]) == 0
    assert freshness.main(["--root", str(tree), "--strict"]) == 1


def test_render_says_so_when_there_is_nothing_to_say(tree):
    assert "No findings" in freshness.render([])
