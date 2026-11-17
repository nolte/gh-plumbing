#!/usr/bin/env python3
"""Refuse area labels in the release-drafter categories and version-resolver.

release-drafter lists a pull request under every category one of its labels
matches. boring-cyborg derives *area* labels from the touched paths, so they
co-occur with the pull request's *type* label. An area label used as a
category label therefore renders a pull request twice: #413 removed
`project-config`, `cicd` and `dependencies` from Maintenance, and #475 found
`documentation` left behind, filing every `fix` that touched `docs/` under
both Bug Fixes and Maintenance.

Predicate: no label in any `categories[*].labels` or
`version-resolver.<level>.labels` of commons-release-drafter.yml is a key of
`labelPRBasedOnFilePath` in commons-boring-cyborg.yml. The selector is the
whole path-label map, so an area label added to boring-cyborg later is covered
without anyone listing it here.
"""

import sys
from pathlib import Path

import yaml

DRAFTER = Path(".github/commons-release-drafter.yml")
CYBORG = Path(".github/commons-boring-cyborg.yml")


def area_labels(cyborg: Path) -> set[str]:
    data = yaml.safe_load(cyborg.read_text()) or {}
    return set((data.get("labelPRBasedOnFilePath") or {}).keys())


def findings(drafter: Path, areas: set[str]) -> list[str]:
    data = yaml.safe_load(drafter.read_text()) or {}
    out: list[str] = []
    for category in data.get("categories") or []:
        for label in category.get("labels") or []:
            if label in areas:
                out.append(f"category '{category.get('title')}' matches area label '{label}'")
    for level, spec in (data.get("version-resolver") or {}).items():
        if not isinstance(spec, dict):
            continue
        for label in spec.get("labels") or []:
            if label in areas:
                out.append(f"version-resolver '{level}' lists area label '{label}'")
    return out


def main() -> int:
    errors = findings(DRAFTER, area_labels(CYBORG))
    if errors:
        print(
            f"{DRAFTER}: area labels from {CYBORG} must not select a release-notes "
            "category or version level -- a pull request then renders under its "
            "type and its area (see #413, #475):",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
