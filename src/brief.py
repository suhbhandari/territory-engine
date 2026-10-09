"""
Phase 4: Account Briefs
Writes a one-page brief per account group in the configured tiers. Every claim in a
brief must cite a numbered fact, every fact carries a source link, and briefs that
fail the citation check are flagged instead of shipped.

Usage:
  python3 src/brief.py [--vertical home_care_post_acute] [--limit N] [--dry-run] [--redo-failed]

Design:
  - Facts are built by code from the scored account row, using the fact templates in the
    vertical's brief.yaml. The model never sees raw data it could misread, and never
    browses: it can only arrange and phrase the facts it is given
  - The model returns structured JSON in which each statement lists the fact ids it rests on
  - Source check (code, not the model): every statement cites at least one fact, every cited
    id exists, and every number in a statement appears in a fact it cites. A brief that
    fails is saved with check_status=failed and the reasons
  - "What we don't know" is written by code from the same data, not by the model
  - One brief per group (accounts sharing a website); sibling locations are listed in it
  - Token usage and cost per brief are logged to briefs_index.csv, saved every few briefs
    so an interrupted run resumes; briefs already written are skipped on re-run
"""

import argparse
import json
import os
import re
import sys
import yaml
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.score import matches  # noqa: E402

load_dotenv(ROOT / ".env")

SCORED_PATH = ROOT / "outputs" / "raw" / "accounts_scored.csv"
BRIEFS_DIR = ROOT / "outputs" / "raw" / "briefs"
INDEX_PATH = BRIEFS_DIR / "briefs_index.csv"
INDEX_COLS = ["account_group", "group_rank", "name", "tier", "score", "file", "check_status", "check_notes",
              "facts", "model", "input_tokens", "output_tokens", "cost_usd", "generated_at"]
MAX_WORKERS = 4
SAVE_EVERY = 20

STATEMENT = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "fact_ids"],
    "additionalProperties": False,
}
BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": STATEMENT,
        "snapshot": {"type": "array", "items": STATEMENT},
        "why_now": {"type": "array", "items": STATEMENT},
        "opening_angle": STATEMENT,
    },
    "required": ["headline", "snapshot", "why_now", "opening_angle"],
    "additionalProperties": False,
}


def _when(conditions, row: dict) -> bool:
    if not conditions:
        return True
    if isinstance(conditions, dict):
        conditions = [conditions]
    return all(matches(c, row) for c in conditions)


def build_facts(row: dict, cfg: dict) -> list:
    facts = []
    for template in cfg["facts"]:
        if not _when(template.get("when"), row):
            continue
        source = cfg["sources"][template["source"]]
        facts.append({
            "id": f"F{len(facts) + 1}",
            "text": template["text"].format(**row),
            "source_label": source["label"].format(**row),
            "source_url": source["url"].format(**row),
        })
    return facts


def build_unknowns(row: dict, cfg: dict) -> list:
    return [u["text"].format(**row) for u in cfg.get("unknowns", []) if _when(u.get("when"), row)]


def _numbers(text: str) -> list:
    return [n.replace(",", "") for n in re.findall(r"\d+(?:,\d{3})*", text)]


def source_check(brief: dict, facts: list, name: str = "") -> list:
    by_id = {f["id"]: f["text"] for f in facts}
    # Digits that are part of the account's own name are not claims.
    name_numbers = set(_numbers(name))
    problems = []
    statements = [("headline", brief["headline"]), ("opening_angle", brief["opening_angle"])]
    statements += [(f"snapshot[{i}]", s) for i, s in enumerate(brief["snapshot"])]
    statements += [(f"why_now[{i}]", s) for i, s in enumerate(brief["why_now"])]

    for where, statement in statements:
        ids = statement["fact_ids"]
        if not ids:
            problems.append(f"{where}: no fact cited")
            continue
        missing = [i for i in ids if i not in by_id]
        if missing:
            problems.append(f"{where}: cites unknown fact {', '.join(missing)}")
            continue
        cited_numbers = set(_numbers(" ".join(by_id[i] for i in ids))) | name_numbers
        for number in _numbers(statement["text"]):
            if number not in cited_numbers:
                problems.append(f"{where}: number {number} is not in the cited facts")
    return problems


def render(row: dict, members: list, brief: dict, facts: list, unknowns: list, problems: list) -> str:
    def line(statement: dict) -> str:
        return f"{statement['text']} [{', '.join(statement['fact_ids'])}]"

    out = [f"# {row['name']}", ""]
    out.append(f"**Tier {row['tier']} · score {row['score']}/100 · rank {row['group_rank']}** · "
               f"data coverage {float(row['data_coverage']):.0%}")
    out.append("")
    if problems:
        out += ["> **Source check failed. Do not use without review.**"] + [f"> - {p}" for p in problems] + [""]
    out += [line(brief["headline"]), "", "## Snapshot"]
    out += [f"- {line(s)}" for s in brief["snapshot"]]
    out += ["", "## Why now"]
    out += [f"- {line(s)}" for s in brief["why_now"]]
    out += ["", "## Opening angle", line(brief["opening_angle"])]
    if len(members) > 1:
        out += ["", "## Locations in this territory"]
        out += [f"- {m['name']}, {m['city']} {m['zip']} · {m['phone']} · score {m['score']}" for m in members]
    else:
        out += ["", "## Contact", f"- {row['address']}, {row['city']} {row['zip']} · {row['phone']}"]
    out += ["", "## What we don't know"]
    out += [f"- {u}" for u in unknowns] or ["- Nothing flagged."]
    out += ["", "## Facts and sources"]
    out += [f"- **{f['id']}** {f['text']} ([{f['source_label']}]({f['source_url']}))" for f in facts]
    out += ["", f"Score breakdown: {row['score_reasons']}", ""]
    return "\n".join(out)


def user_prompt(row: dict, members: list, facts: list) -> str:
    lines = [f"Account: {row['name']}", "", "Facts:"]
    lines += [f"{f['id']}: {f['text']}" for f in facts]
    return "\n".join(lines)


def generate(client, cfg: dict, system: str, prompt: str):
    response = client.beta.messages.create(
        model=cfg["model"],
        max_tokens=16000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": cfg["effort"], "format": {"type": "json_schema", "schema": BRIEF_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason != "end_turn":
        raise RuntimeError(f"model stopped with {response.stop_reason}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.usage, response.model


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def main(vertical: str, limit, dry_run: bool, redo_failed: bool) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    cfg = yaml.safe_load(open(vdir / "brief.yaml"))
    system = (vdir / "brief_prompt.md").read_text()

    scored = pd.read_csv(SCORED_PATH, dtype=str, keep_default_na=False)
    groups = {g: d.to_dict("records") for g, d in scored.groupby("account_group", sort=False)}
    leads = [m[0] for m in groups.values() if m[0]["tier"] in cfg["tiers"]]

    index = pd.read_csv(INDEX_PATH, dtype=str, keep_default_na=False) if INDEX_PATH.exists() else pd.DataFrame(columns=INDEX_COLS)
    keep = index["check_status"].isin(["passed"] if redo_failed else ["passed", "failed"])
    done = set(index.loc[keep, "account_group"])
    todo = [r for r in leads if r["account_group"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"[brief] {len(leads)} groups in tiers {cfg['tiers']} | {len(leads) - len([r for r in leads if r['account_group'] not in done])} already written | {len(todo)} to write")

    def work(row: dict) -> dict:
        members = groups[row["account_group"]]
        row = dict(row, sibling_count=str(len(members) - 1))
        facts = build_facts(row, cfg)
        unknowns = build_unknowns(row, cfg)
        prompt = user_prompt(row, members, facts)
        entry = {"account_group": row["account_group"], "group_rank": row["group_rank"], "name": row["name"],
                 "tier": row["tier"], "score": row["score"], "facts": len(facts), "model": cfg["model"],
                 "generated_at": datetime.now(timezone.utc).isoformat()}
        if dry_run:
            return dict(entry, _prompt=prompt, _unknowns=unknowns)
        try:
            brief, usage, model = generate(client, cfg, system, prompt)
        except Exception as exc:
            return dict(entry, check_status="error", check_notes=f"{type(exc).__name__}: {exc}"[:300])
        problems = source_check(brief, facts, row["name"])
        path = BRIEFS_DIR / f"{int(row['group_rank']):04d}-{slug(row['name'])}.md"
        path.write_text(render(row, members, brief, facts, unknowns, problems))
        price = cfg["price_per_mtok"]
        cost = (usage.input_tokens * price["input"] + usage.output_tokens * price["output"]) / 1_000_000
        return dict(entry, file=path.name, model=model, check_status="failed" if problems else "passed",
                    check_notes=" | ".join(problems), input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens, cost_usd=round(cost, 4))

    if dry_run:
        for result in map(work, todo[:limit or 2]):
            print(f"\n--- {result['name']} ({result['facts']} facts) ---\n{result['_prompt']}\nUnknowns: {result['_unknowns']}")
        return
    if not todo:
        return

    # Keys that are not tied to one workspace must name the workspace on every request.
    workspace = os.getenv("ANTHROPIC_WORKSPACE_ID")
    client = anthropic.Anthropic(default_headers={"anthropic-workspace-id": workspace} if workspace else None)
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for start in range(0, len(todo), SAVE_EVERY):
            batch = list(pool.map(work, todo[start:start + SAVE_EVERY]))
            results.extend(batch)
            index = index[~index["account_group"].isin([r["account_group"] for r in batch])]
            index = pd.concat([index, pd.DataFrame(batch, columns=INDEX_COLS).astype(object)], ignore_index=True)
            index.to_csv(INDEX_PATH, index=False)
            print(f"[brief] {len(results)}/{len(todo)} written, saved", flush=True)

    new = pd.DataFrame(results, columns=INDEX_COLS)
    print(f"[brief] this run: {new['check_status'].value_counts().to_dict()}")
    cost = pd.to_numeric(new["cost_usd"], errors="coerce")
    if cost.notna().any():
        print(f"[brief] cost this run: ${cost.sum():.2f} total, ${cost.mean():.4f} per brief")
    for _, r in new[new["check_status"] != "passed"].head(5).iterrows():
        print(f"  {r['check_status']}: {r['name']}: {r['check_notes']}")
    print(f"[brief] Written → {BRIEFS_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default="home_care_post_acute")
    parser.add_argument("--limit", type=int, default=None, help="Write only the first N briefs")
    parser.add_argument("--dry-run", action="store_true", help="Print the facts and prompt; call nothing")
    parser.add_argument("--redo-failed", action="store_true", help="Regenerate briefs that failed the source check")
    args = parser.parse_args()
    main(args.vertical, args.limit, args.dry_run, args.redo_failed)
