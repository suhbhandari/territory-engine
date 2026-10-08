#!/usr/bin/env python3
"""
check_generic.py
Fails if any vertical-specific terms are found in core code.
Core = everything except config/verticals/, tests/fixtures/, outputs/, and this script.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

EXCLUDED_PREFIXES = [
    "config/verticals/",
    "tests/fixtures/",
    "outputs/",
    "scripts/check_generic.py",
    "CLAUDE.md",
    ".env",
]

SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".md", ".json", ".txt"}

# Case-insensitive terms: plain English phrases and abbreviations found in vertical config
TERMS_ICASE = [
    r"\bcaregiver\b",
    r"home\s+health",   # catches "home health" in prose/comments but not identifiers like home_health_foo
    r"home\s+care",     # same — "home care" in prose only
    r"\bhospice\b",
    r"\bHHA\b",
    r"\bCNA\b",
    r"right\s+at\s+home",
    r"visiting\s+angels",
    r"\barya\b",
    r"post\s+acute",
]

# Case-sensitive terms: acronyms that need exact casing to avoid URL false-positives
# e.g. "npiregistry.cms.hhs.gov" is a source URL, not a vertical concept
TERMS_CASE = [
    r"\bCMS\b",
]

pattern_icase = re.compile("|".join(TERMS_ICASE), re.IGNORECASE)
pattern_case = re.compile("|".join(TERMS_CASE))


def is_excluded(relative: Path) -> bool:
    s = str(relative)
    return any(s.startswith(ex) or s == ex for ex in EXCLUDED_PREFIXES)


def main() -> int:
    failures: list[str] = []

    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in SCAN_EXTENSIONS:
            continue
        relative = path.relative_to(ROOT)
        if is_excluded(relative):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for i, line in enumerate(text.splitlines(), 1):
            if pattern_icase.search(line) or pattern_case.search(line):
                failures.append(f"  {relative}:{i}: {line.strip()}")

    print("=== check-generic ===")
    if failures:
        print(f"FAIL — {len(failures)} match(es) in core code:")
        for f in failures:
            print(f)
        return 1
    else:
        print("PASS — no vertical-specific terms found in core code")
        return 0


if __name__ == "__main__":
    sys.exit(main())
