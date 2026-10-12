"""
Phase 6: Export
Writes import-ready CSV files for the CRM and the sales engagement tool, as described by
the vertical's export.yaml. Calls no external service.

Usage:
  python3 src/export.py [--vertical <name>]

Design:
  - Each target in export.yaml is one CSV: which rows it holds (every account, or one row
    per account group), which tiers, and an ordered list of columns. A column value is a
    template over the scored account's fields, so adding or renaming a CRM field is a
    config edit
  - Group rows also carry that group's outreach touches as fields named
    <touch>_subject, <touch>_body, <touch>_core and <touch>_script. The _core form has the
    greeting and sign-off removed, because a sending tool's template supplies those with
    its own merge fields; a merge field stored inside a field value is not filled in.
    The _script form swaps merge fields for bracketed words, for text a rep reads aloud
  - Sequences that failed their checks are never exported
  - Every file is UTF-8 with a header row; both tools map columns to fields at import,
    so headers are labels to map from, not API names
"""

import argparse
import re
import sys
import yaml
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import DEFAULT_VERTICAL  # noqa: E402

SCORED_PATH = ROOT / "outputs" / "raw" / "accounts_scored.csv"
TOUCHES_PATH = ROOT / "outputs" / "raw" / "sequences" / "sequences.csv"
BRIEFS_INDEX_PATH = ROOT / "outputs" / "raw" / "briefs" / "briefs_index.csv"
OUT_DIR = ROOT / "outputs" / "raw" / "exports"

_GREETING = re.compile(r"^\s*(?:hi|hello|hey)?\s*\{\{[^}]+\}\}\s*[,.:]?\s*", re.I)
_SIGN_OFF = re.compile(r"\n+\s*\{\{[^}]+\}\}\s*$")
_MERGE_FIELD = re.compile(r"\{\{[^}]+\}\}")


class _Blank(dict):
    def __missing__(self, key):
        return ""


def touch_fields(touches: pd.DataFrame, touch_ids: list, merge_map: dict, script_map: dict) -> dict:
    """{account_group: {<touch>_subject/_body/_core/_script: text}} for sequences that passed."""
    fields = {}
    passed = touches[touches["check_status"] == "passed"]
    for row in passed.to_dict("records"):
        touch_id = touch_ids[int(row["touch"]) - 1]
        body = row["body"]
        core = _SIGN_OFF.sub("", _GREETING.sub("", body)).strip()
        core = core[:1].upper() + core[1:]
        script = body
        for ours, spoken in script_map.items():
            script = script.replace(ours, spoken)
        for ours, theirs in merge_map.items():
            body = body.replace(ours, theirs)
            core = core.replace(ours, theirs)
        group = fields.setdefault(row["account_group"], {"persona": row["persona"]})
        group[f"{touch_id}_subject"] = row["subject"]
        group[f"{touch_id}_body"] = body
        group[f"{touch_id}_core"] = core
        group[f"{touch_id}_script"] = script
    return fields


def build_target(target: dict, scored: pd.DataFrame, extras: dict) -> pd.DataFrame:
    rows = scored[scored["tier"].isin(target["tiers"])]
    if target["rows"] == "groups":
        rows = rows[rows["rank_in_group"] == "1"]
        if target.get("require"):
            rows = rows[rows["account_group"].map(lambda g: bool(extras.get(g, {}).get(target["require"])))]
    out = []
    for row in rows.to_dict("records"):
        context = _Blank(row)
        if target["rows"] == "groups":
            context.update(extras.get(row["account_group"], {}))
        out.append({col["header"]: col["value"].format_map(context).strip() for col in target["columns"]})
    return pd.DataFrame(out, columns=[c["header"] for c in target["columns"]])


def main(vertical: str) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    cfg = yaml.safe_load(open(vdir / "export.yaml"))
    touch_ids = [t["id"] for t in yaml.safe_load(open(vdir / "sequence.yaml"))["touches"]]

    scored = pd.read_csv(SCORED_PATH, dtype=str, keep_default_na=False)
    extras = {}
    if TOUCHES_PATH.exists():
        touches = pd.read_csv(TOUCHES_PATH, dtype=str, keep_default_na=False)
        extras = touch_fields(touches, touch_ids, cfg.get("merge_field_map", {}), cfg.get("script_placeholders", {}))
    if BRIEFS_INDEX_PATH.exists():
        briefs = pd.read_csv(BRIEFS_INDEX_PATH, dtype=str, keep_default_na=False)
        for b in briefs[briefs["check_status"] == "passed"].to_dict("records"):
            extras.setdefault(b["account_group"], {})["brief_file"] = b["file"]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, target in cfg["targets"].items():
        df = build_target(target, scored, extras)
        problems = []
        key = target.get("unique_key")
        if key and df[key].duplicated().any():
            problems.append(f"{int(df[key].duplicated().sum())} duplicate values in '{key}'")
        for header in target.get("required", []):
            blank = int((df[header] == "").sum())
            if blank:
                problems.append(f"{blank} rows with blank '{header}'")
        leftover = int(df.apply(lambda col: col.str.contains(_MERGE_FIELD)).any(axis=1).sum()) if target.get("no_merge_fields") else 0
        if leftover:
            problems.append(f"{leftover} rows still contain a merge field inside a field value")

        path = OUT_DIR / target["file"]
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"[export] {name}: {len(df)} rows × {len(df.columns)} columns → {path.relative_to(ROOT)}")
        for p in problems:
            print(f"  WARNING: {p}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    args = parser.parse_args()
    main(args.vertical)
