"""
Phase 5: Outreach Sequences
Drafts a short outreach sequence per account group, built on the same numbered facts as
the brief. Every touch must cite the facts it uses, and drafts that break the rules are
flagged for review instead of shipped.

Usage:
  python3 src/sequence.py [--vertical <name>] [--limit N] [--dry-run] [--redo-failed]

Design:
  - The touches (channel, day, purpose, word limit) come from the vertical's sequence.yaml,
    so the cadence is config, not code
  - The persona each sequence is written for is chosen by the first matching rule in
    personas.yaml. No contact names are collected, so drafts use merge fields
    (e.g. {{first_name}}) for the sending tool to fill
  - Checks (code, not the model): every touch cites at least one real fact; every number and
    every capitalised word inside a sentence appears in a fact it cites (see brief.py); each touch is within its word limit; a touch that
    takes a subject has one within the length limit; only the allowed merge fields appear
  - Output is one readable file per group plus sequences.csv with one row per touch, which
    is what the export step reads
"""

import argparse
import re
import sys
import yaml
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.settings import DEFAULT_VERTICAL  # noqa: E402

from src.brief import _when, build_facts, check_statements, forbidden_words, render_fact, slug  # noqa: E402
from src.current import current_sequences  # noqa: E402
from src.llm import cost_usd, generate_json, load_prompt, make_client  # noqa: E402

SCORED_PATH = ROOT / "outputs" / "raw" / "accounts_scored.csv"
OUT_DIR = ROOT / "outputs" / "raw" / "sequences"
INDEX_PATH = OUT_DIR / "sequences_index.csv"
TOUCHES_PATH = OUT_DIR / "sequences.csv"
INDEX_COLS = ["account_group", "group_rank", "name", "tier", "score", "persona", "file", "check_status",
              "check_notes", "model", "input_tokens", "output_tokens", "cost_usd", "generated_at"]
TOUCH_COLS = ["account_group", "group_rank", "name", "tier", "persona", "touch", "channel", "day",
              "subject", "body", "fact_ids", "word_count", "check_status"]
MAX_WORKERS = 4
SAVE_EVERY = 20
WORD_TARGET_RATIO = 0.85

SCHEMA = {
    "type": "object",
    "properties": {
        "touches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "touch_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["touch_id", "subject", "body", "fact_ids"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["touches"],
    "additionalProperties": False,
}


def pick_persona(row: dict, personas: list) -> dict:
    for persona in personas:
        if _when(persona.get("when"), row):
            return persona
    raise ValueError("personas.yaml needs a final persona with no `when`")


def user_prompt(row: dict, facts: list, persona: dict, cfg: dict) -> str:
    lines = [f"Account: {row['name']}", "",
             f"Write to: {persona['title']}", f"What this person cares about: {persona['cares_about'].strip()}", "",
             "Facts:"]
    lines += [f"{f['id']}: {f['text']}" for f in facts]
    lines += ["", "Touches to write, in this order:"]
    for t in cfg["touches"]:
        subject = f", subject of {int(cfg['subject_max_chars'] * WORD_TARGET_RATIO)} characters or fewer" if t.get("subject") else ", subject empty"
        # The model counts words loosely, so it is given a target below the enforced limit.
        target = int(t["max_words"] * WORD_TARGET_RATIO)
        lines.append(f"- touch_id \"{t['id']}\" ({t['channel']}, day {t['day']}, aim for {target} words or fewer{subject}): {t['purpose'].strip()}")
    lines += ["", f"Allowed merge fields: {', '.join(cfg['merge_fields'])}"]
    return "\n".join(lines)


def check(result: dict, facts: list, row: dict, cfg: dict, allowed=(), facts_cfg=None) -> list:
    by_id = {t["touch_id"]: t for t in result["touches"]}
    facts_cfg = facts_cfg or {}
    problems = []
    statements = []
    for spec in cfg["touches"]:
        touch = by_id.get(spec["id"])
        if touch is None:
            problems.append(f"{spec['id']}: missing")
            continue
        text = f"{touch['subject']} {touch['body']}"
        statements.append((spec["id"], {"text": text, "fact_ids": touch["fact_ids"]}))
        words = len(touch["body"].split())
        if words > spec["max_words"]:
            problems.append(f"{spec['id']}: {words} words, limit {spec['max_words']}")
        if not spec.get("subject"):
            if touch["subject"].strip():
                problems.append(f"{spec['id']}: subject should be empty")
        elif not touch["subject"].strip():
            problems.append(f"{spec['id']}: no subject")
        elif len(touch["subject"]) > cfg["subject_max_chars"]:
            problems.append(f"{spec['id']}: subject is {len(touch['subject'])} characters, limit {cfg['subject_max_chars']}")
        for field in re.findall(r"\{\{[^}]*\}\}", text):
            if field not in cfg["merge_fields"]:
                problems.append(f"{spec['id']}: merge field {field} is not allowed")
    extra = set(by_id) - {t["id"] for t in cfg["touches"]}
    if extra:
        problems.append(f"unexpected touches: {', '.join(sorted(extra))}")
    for spec in cfg["touches"]:
        touch = by_id.get(spec["id"])
        if touch is None:
            continue
        for word in forbidden_words(f"{touch['subject']} {touch['body']}", cfg.get("outreach_forbidden_words", [])):
            problems.append(f"{spec['id']}: '{word}' is the engine's own vocabulary, not a seller's")
    return problems + check_statements(statements, facts, row["name"], allowed,
                                       facts_cfg.get("hedges", []), facts_cfg.get("claim_words", []))


def touch_rows(row: dict, persona: dict, result: dict, cfg: dict, status: str) -> list:
    by_id = {t["touch_id"]: t for t in result["touches"]}
    rows = []
    for n, spec in enumerate(cfg["touches"], 1):
        touch = by_id.get(spec["id"])
        if touch is None:
            continue
        rows.append({
            "account_group": row["account_group"], "group_rank": row["group_rank"], "name": row["name"],
            "tier": row["tier"], "persona": persona["title"], "touch": n, "channel": spec["channel"],
            "day": spec["day"], "subject": touch["subject"], "body": touch["body"],
            "fact_ids": " ".join(touch["fact_ids"]), "word_count": len(touch["body"].split()),
            "check_status": status,
        })
    return rows


def render(row: dict, persona: dict, rows: list, facts: list, problems: list) -> str:
    out = [f"# {row['name']}", "",
           f"**Tier {row['tier']} · rank {row['group_rank']}** · written for: {persona['title']}", ""]
    if problems:
        out += ["> **Checks failed. Do not send without review.**"] + [f"> - {p}" for p in problems] + [""]
    for r in rows:
        out += [f"## Touch {r['touch']}: {r['channel']}, day {r['day']}", ""]
        if r["subject"]:
            out += [f"**Subject:** {r['subject']}", ""]
        out += [r["body"], "", f"_Rests on: {r['fact_ids']} · {r['word_count']} words_", ""]
    out += ["## Facts and sources"]
    out += [render_fact(f) for f in facts]
    return "\n".join(out) + "\n"


def main(vertical: str, limit, dry_run: bool, redo_failed: bool) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    cfg = yaml.safe_load(open(vdir / "sequence.yaml"))
    facts_cfg = yaml.safe_load(open(vdir / "brief.yaml"))
    personas = yaml.safe_load(open(vdir / "personas.yaml"))["personas"]
    system = load_prompt(vdir, "sequence_prompt.md")

    scored = pd.read_csv(SCORED_PATH, dtype=str, keep_default_na=False)
    leads = scored[(scored["rank_in_group"] == "1") & scored["tier"].isin(cfg["tiers"])].to_dict("records")

    index = pd.read_csv(INDEX_PATH, dtype=str, keep_default_na=False) if INDEX_PATH.exists() else pd.DataFrame(columns=INDEX_COLS)
    touches = pd.read_csv(TOUCHES_PATH, dtype=str, keep_default_na=False) if TOUCHES_PATH.exists() else pd.DataFrame(columns=TOUCH_COLS)
    current, stale = current_sequences(index, touches, scored, cfg, facts_cfg, OUT_DIR)
    done = set(current.loc[current["check_status"].isin(["passed"] if redo_failed else ["passed", "failed"]), "account_group"])
    todo = [r for r in leads if r["account_group"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"[sequence] {len(leads)} groups in tiers {cfg['tiers']} | {len([r for r in leads if r['account_group'] in done])} already written | "
          f"{len(stale)} out of date ({', '.join(sorted(set(stale.values()))) or 'none'}) | {len(todo)} to write")

    def work(row: dict):
        facts = build_facts(row, facts_cfg)
        persona = pick_persona(row, personas)
        prompt = user_prompt(row, facts, persona, cfg)
        entry = {"account_group": row["account_group"], "group_rank": row["group_rank"], "name": row["name"],
                 "tier": row["tier"], "score": row["score"], "persona": persona["title"], "model": cfg["model"],
                 "generated_at": datetime.now(timezone.utc).isoformat()}
        if dry_run:
            return dict(entry, _prompt=prompt), []
        try:
            result, usage, model = generate_json(client, cfg, system, prompt, SCHEMA)
        except Exception as exc:
            return dict(entry, check_status="error", check_notes=f"{type(exc).__name__}: {exc}"[:300]), []
        problems = check(result, facts, row, cfg, facts_cfg.get("allowed_words", []), facts_cfg)
        status = "failed" if problems else "passed"
        rows = touch_rows(row, persona, result, cfg, status)
        path = OUT_DIR / f"{int(row['group_rank']):04d}-{slug(row['name'])}.md"
        path.write_text(render(row, persona, rows, facts, problems))
        return dict(entry, file=path.name, model=model, check_status=status, check_notes=" | ".join(problems),
                    input_tokens=usage.input_tokens, output_tokens=usage.output_tokens,
                    cost_usd=cost_usd(usage, cfg["price_per_mtok"])), rows

    if dry_run:
        for entry, _ in map(work, todo[:limit or 2]):
            print(f"\n--- {entry['name']} → {entry['persona']} ---\n{entry['_prompt']}")
        return
    if not todo:
        return

    client = make_client()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for start in range(0, len(todo), SAVE_EVERY):
            batch = list(pool.map(work, todo[start:start + SAVE_EVERY]))
            batch_groups = [e["account_group"] for e, _ in batch]
            entries.extend(e for e, _ in batch)
            index = index[~index["account_group"].isin(batch_groups)]
            index = pd.concat([index, pd.DataFrame([e for e, _ in batch], columns=INDEX_COLS).astype(object)], ignore_index=True)
            touches = touches[~touches["account_group"].isin(batch_groups)]
            new_rows = [r for _, rows in batch for r in rows]
            if new_rows:
                touches = pd.concat([touches, pd.DataFrame(new_rows, columns=TOUCH_COLS).astype(object)], ignore_index=True)
            index.to_csv(INDEX_PATH, index=False)
            touches.to_csv(TOUCHES_PATH, index=False)
            print(f"[sequence] {len(entries)}/{len(todo)} written, saved", flush=True)

    new = pd.DataFrame(entries, columns=INDEX_COLS)
    print(f"[sequence] this run: {new['check_status'].value_counts().to_dict()}")
    cost = pd.to_numeric(new["cost_usd"], errors="coerce")
    if cost.notna().any():
        print(f"[sequence] cost this run: ${cost.sum():.2f} total, ${cost.mean():.4f} per sequence")
    for _, r in new[new["check_status"] != "passed"].head(8).iterrows():
        print(f"  {r['check_status']}: {r['name']}: {str(r['check_notes'])[:220]}")
    print(f"[sequence] Written → {OUT_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--limit", type=int, default=None, help="Write only the first N sequences")
    parser.add_argument("--dry-run", action="store_true", help="Print the prompt; call nothing")
    parser.add_argument("--redo-failed", action="store_true", help="Regenerate sequences that failed their checks")
    args = parser.parse_args()
    main(args.vertical, args.limit, args.dry_run, args.redo_failed)
