#!/usr/bin/env python3
"""
agreement.py
How closely a person's grades of the briefs and drafts agree with each model grading round.

Reads the hand-grading sheet (outputs/private/hand_grades.md: one "## G<n>:" section per
item, each with "- <Dimension> (1-5): <n>" lines and "- First this week? (...): <answer>")
and each model round's CSV (columns id, brief_accuracy, brief_usefulness, draft_accuracy,
draft_sendability, first_this_week). For each 1-5 dimension it reports exact agreement,
agreement within one point, and both means; for "first this week" it reports exact
agreement. Items are matched by id (G1, G2, ...), never by name.

Writes counts and percentages only to outputs/raw/agreement.json, which the report card
reads. The grades themselves, and the names in the sheet, stay in outputs/private/.

Usage:
  python3 scripts/agreement.py [--hand PATH] [--round LABEL=PATH[=same|different]] ...
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW  # noqa: E402

PRIVATE = ROOT / "outputs" / "private"
OUTPUT_PATH = RAW / "agreement.json"

DIMENSIONS = {
    "brief_accuracy": "Brief accuracy",
    "brief_usefulness": "Brief usefulness",
    "draft_accuracy": "Draft accuracy",
    "draft_sendability": "Draft sendability",
}
FIRST = ("first_this_week", "First this week?")
# Round label, model grade file, and whether the model graded the same text the person did.
DEFAULT_ROUNDS = [
    ("round 1", PRIVATE / "model_grades.csv", "different"),
    ("round 2", PRIVATE / "model_grades_round2.csv", "same"),
]
_SECTION = re.compile(r"^## (G\d+):", re.M)


def parse_sheet(text: str) -> tuple:
    """({id: {dimension: value}}, [missing "id field" strings]) from a filled-in sheet."""
    starts = [(m.group(1), m.start()) for m in _SECTION.finditer(text)]
    grades, missing = {}, []
    for i, (item, start) in enumerate(starts):
        chunk = text[start:starts[i + 1][1] if i + 1 < len(starts) else len(text)]
        row = {}
        for key, label in [*DIMENSIONS.items(), FIRST]:
            m = re.search(rf"^- {re.escape(label)} \([^)]*\):[ \t]*(.*)$", chunk, re.M)
            value = m.group(1).strip() if m else ""
            if key == FIRST[0]:
                value = value.lower()
                if value not in ("yes", "no", "not sure"):
                    missing.append(f"{item} {label}")
                    continue
            else:
                n = re.match(r"([1-5])\b", value)
                if not n:
                    missing.append(f"{item} {label}")
                    continue
                value = int(n.group(1))
            row[key] = value
        grades[item] = row
    return grades, missing


def compare(hand: dict, model: pd.DataFrame) -> dict:
    model = model.set_index("id")
    common = [i for i in hand if i in model.index]
    out = {"items": len(common), "dimensions": {}}
    for key, label in DIMENSIONS.items():
        h = pd.Series([hand[i][key] for i in common], dtype=float)
        m = pd.to_numeric(model.loc[common, key], errors="coerce").reset_index(drop=True)
        diff = (h - m).abs()
        out["dimensions"][key] = {
            "label": label,
            "exact_pct": round(100 * float((diff == 0).mean()), 1),
            "within_one_pct": round(100 * float((diff <= 1).mean()), 1),
            "hand_mean": round(float(h.mean()), 2),
            "model_mean": round(float(m.mean()), 2),
        }
    h = [hand[i][FIRST[0]] for i in common]
    m = [str(v).strip().lower() for v in model.loc[common, FIRST[0]]]
    out["first_this_week"] = {
        "exact_pct": round(100 * sum(a == b for a, b in zip(h, m)) / len(common), 1),
        "hand_yes": h.count("yes"),
        "model_yes": m.count("yes"),
    }
    return out


def main(hand_path: Path, rounds: list, output_path: Path = OUTPUT_PATH) -> dict:
    if not hand_path.exists():
        raise SystemExit(f"{hand_path} not found")
    hand, missing = parse_sheet(hand_path.read_text())
    if not hand:
        raise SystemExit(f"no '## G<n>:' sections in {hand_path}")
    if missing:
        raise SystemExit(f"{len(missing)} grades are blank or not readable in {hand_path.name} "
                         f"(is the file saved?). First few: {', '.join(missing[:6])}")
    result = {"hand_items": len(hand), "rounds": []}
    for label, path, text in rounds:
        if not Path(path).exists():
            print(f"[agreement] {label}: {path} not found, skipped")
            continue
        model = pd.read_csv(path, dtype=str, keep_default_na=False)
        result["rounds"].append({"round": label, "same_text": text == "same", **compare(hand, model)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2))

    print(f"[agreement] {len(hand)} items graded by hand")
    for r in result["rounds"]:
        print(f"  model {r['round']} ({'same text' if r['same_text'] else 'earlier text'}, {r['items']} items):")
        for d in r["dimensions"].values():
            print(f"    {d['label']}: exact {d['exact_pct']}% | within one {d['within_one_pct']}% | "
                  f"mean hand {d['hand_mean']} vs model {d['model_mean']}")
        f = r["first_this_week"]
        print(f"    First this week: agree {f['exact_pct']}% | yes: hand {f['hand_yes']}, model {f['model_yes']}")
    print(f"[agreement] Written → {output_path} (numbers only)")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hand", type=Path, default=PRIVATE / "hand_grades.md")
    parser.add_argument("--round", action="append", default=[],
                        help="LABEL=PATH or LABEL=PATH=same|different (default: the two model rounds)")
    args = parser.parse_args()
    rounds = [tuple((r.split("=") + ["different"])[:3]) for r in args.round] or DEFAULT_ROUNDS
    main(args.hand, rounds)
