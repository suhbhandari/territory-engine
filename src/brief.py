"""
Phase 4: Account Briefs
Writes a one-page brief per account group in the configured tiers. Every claim in a
brief must cite a numbered fact, every fact carries a source link, and briefs that
fail the citation check are flagged instead of shipped.

Usage:
  python3 src/brief.py [--vertical <name>] [--limit N] [--dry-run] [--redo-failed]

Design:
  - Facts are built by code from the scored account row, using the fact templates in the
    vertical's brief.yaml. The model never sees raw data it could misread, and never
    browses: it can only arrange and phrase the facts it is given
  - The model returns structured JSON in which each statement lists the fact ids it rests on
  - Source check (code, not the model): every statement cites at least one fact, every cited
    id exists, every number in a statement (in digits, or a number word from two up) appears
    in a fact it cites, and every capitalised word inside a sentence (a place, an
    organisation, a job title) appears in a fact it cites or in the vertical's
    allowed_words. A brief that fails is saved with check_status=failed and the reasons
  - Each fact carries its source link and, where the source config names a date column,
    the date that data was collected
  - "What we don't know" is written by code from the same data, not by the model
  - One brief per group (accounts sharing a website); sibling locations are listed in it
  - Token usage and cost per brief are logged to briefs_index.csv, saved every few briefs
    so an interrupted run resumes; briefs already written are skipped on re-run
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

from src.llm import cost_usd, generate_json, load_prompt, make_client  # noqa: E402
from src.score import matches  # noqa: E402

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
    row = dict(row)
    for column in cfg.get("title_case_columns", []):
        if column in row:
            row[column] = smart_title(str(row[column]))
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
            "as_of": str(row.get(source.get("date_column", ""), ""))[:10],
        })
    return facts


def render_fact(fact: dict) -> str:
    """'- **F1** text ([label](url), checked YYYY-MM-DD)'; no link when the source has no URL."""
    source = f"[{fact['source_label']}]({fact['source_url']})" if fact["source_url"] else fact["source_label"]
    if fact.get("as_of"):
        source += f", checked {fact['as_of']}"
    return f"- **{fact['id']}** {fact['text']} ({source})"


_FACT_LINE = re.compile(r"^- \*\*(F\d+)\*\* (.*) \((?:\[(.*?)\]\((.*?)\)|([^()]*?))(?:, checked ([\d-]+))?\)\s*$")


def parse_fact_line(line: str):
    """Inverse of render_fact: {id, text, source_label, source_url, as_of}, or None."""
    m = _FACT_LINE.match(line)
    if not m:
        return None
    return {"id": m.group(1), "text": m.group(2), "source_label": m.group(3) if m.group(3) is not None else m.group(5),
            "source_url": m.group(4) or "", "as_of": m.group(6) or ""}


def build_unknowns(row: dict, cfg: dict) -> list:
    return [u["text"].format(**row) for u in cfg.get("unknowns", []) if _when(u.get("when"), row)]


def _numbers(text: str) -> list:
    return [n.replace(",", "") for n in re.findall(r"\d+(?:,\d{3})*", text)]


def source_check(brief: dict, facts: list, name: str = "", allowed=(), hedges=(), claims=()) -> list:
    statements = [("headline", brief["headline"]), ("opening_angle", brief["opening_angle"])]
    statements += [(f"snapshot[{i}]", s) for i, s in enumerate(brief["snapshot"])]
    statements += [(f"why_now[{i}]", s) for i, s in enumerate(brief["why_now"])]
    return check_statements(statements, facts, name, allowed, hedges, claims)


# The renderer writes these headings and the reader splits on them. They are named once so
# a change to the wording cannot silently stop the reader from finding the end of the
# statements, which would make every line below look like a statement with no citation.
MEMBERS_HEADING = "## Accounts sharing this website domain"
CONTACT_HEADING = "## Contact"


def saved_statements(markdown: str) -> list:
    """Statements read back from a rendered brief, as [(section, {"text", "fact_ids"})].
    A line the renderer would not have written is returned with no fact ids, so it fails."""
    body = markdown.split(MEMBERS_HEADING)[0].split(CONTACT_HEADING)[0]
    section, statements = "headline", []
    for line in body.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if not line.strip() or line.startswith(("# ", "**Tier", ">")):
            continue
        m = re.match(r"^(.*) \[(F\d+(?:, F\d+)*)\]\s*$", line.lstrip("- ").strip())
        statements.append((section, {"text": m.group(1), "fact_ids": m.group(2).split(", ")} if m
                           else {"text": line, "fact_ids": []}))
    return statements


_NUMBER_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                 "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
                 "forty": 40, "fifty": 50, "hundred": 100, "dozen": 12}
_NUMBER_WORD = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.I)
_CAPITALISED = re.compile(r"(?<![\w{])([A-Z][A-Za-z'’-]{2,})")


def unsupported_words(text: str, source_text: str, allowed=()) -> list:
    """Capitalised words inside a sentence that the source text does not contain, and number
    words whose value is not in it. Sentence-initial words, 'I'm'-style contractions and
    words in `allowed` are skipped. Matching ignores case."""
    source = source_text.lower()
    allowed = {a.lower() for a in allowed}
    found = []
    for m in _CAPITALISED.finditer(text):
        before = text[:m.start()].rstrip()
        if not before or before[-1] in ".!?:\n•" or before.endswith("}}") or before.endswith("}},"):
            continue
        if re.match(r"I['’]", m.group(1)):
            continue
        for part in re.split(r"[-–]", re.sub(r"['’]s$", "", m.group(1))):
            if len(part) >= 3 and part[0].isupper() and part.lower() not in source and part.lower() not in allowed:
                found.append(part)
    digits = set(_numbers(source_text))
    for m in _NUMBER_WORD.finditer(text):
        if str(_NUMBER_WORDS[m.group(1).lower()]) not in digits and m.group(1).lower() not in source:
            found.append(m.group(1).lower())
    return found


_SENTENCE = re.compile(r"[^.!?\n]+")


def hedged_claims(text: str, hedges=(), claims=()) -> list:
    """Sentences where a hedge word introduces a claim the cited facts cannot support.

    "Runs hiring through CareerPlug, which suggests recruiting is ongoing" states something
    no source said. The citation and number checks cannot see it: the words are lowercase
    and there is no number in them. The rule here is positional rather than semantic, so it
    stays simple and generic: a hedge word followed in the same sentence by a word naming
    the thing being claimed is a guess written as a finding. Both lists are
    vertical-specific and come from the vertical's config.
    """
    if not hedges or not claims:
        return []
    hedge_re = re.compile(r"\b(" + "|".join(re.escape(h) for h in hedges) + r")\b", re.I)
    claim_re = re.compile(r"\b(" + "|".join(re.escape(c) for c in claims) + r")", re.I)
    found = []
    for sentence in _SENTENCE.findall(text):
        hedge = hedge_re.search(sentence)
        if not hedge:
            continue
        claim = claim_re.search(sentence, hedge.end())
        if claim:
            found.append(f"'{hedge.group(1).lower()} ... {claim.group(0).lower()}'")
    return found


def forbidden_words(text: str, words=()) -> list:
    """Words that must not appear in text a seller sends, however true they are.

    The engine's own vocabulary (its territory, its list, its accounts) describes how the
    engine sees the world, not how a buyer does. A draft carrying it reads as a database
    export. The list is vertical-specific and comes from config.
    """
    found = [w for w in words if re.search(r"\b" + re.escape(w) + r"\b", text, re.I)]
    return list(dict.fromkeys(found))


def smart_title(value: str) -> str:
    """Title-case a value that arrives in capitals, leaving anything else alone.

    Public registries store street addresses in capitals. Copied straight into a draft,
    "180 W 80TH ST" announces that a machine wrote it.
    """
    if not value or not value.isupper():
        return value
    out = re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), value)
    return re.sub(r"(?<=\d)(St|Nd|Rd|Th)\b", lambda m: m.group(0).lower(), out)


def check_statements(statements: list, facts: list, name: str = "", allowed=(),
                     hedges=(), claims=()) -> list:
    """statements: [(label, {"text": str, "fact_ids": [str]})]. Returns a list of problems."""
    by_id = {f["id"]: f["text"] for f in facts}
    # Digits that are part of the account's own name are not claims.
    name_numbers = set(_numbers(name))
    problems = []

    for where, statement in statements:
        ids = statement["fact_ids"]
        if not ids:
            problems.append(f"{where}: no fact cited")
            continue
        missing = [i for i in ids if i not in by_id]
        if missing:
            problems.append(f"{where}: cites unknown fact {', '.join(missing)}")
            continue
        cited = " ".join(by_id[i] for i in ids)
        cited_numbers = set(_numbers(cited)) | name_numbers
        for number in _numbers(statement["text"]):
            if number not in cited_numbers:
                problems.append(f"{where}: number {number} is not in the cited facts")
        for word in dict.fromkeys(unsupported_words(statement["text"], cited + " " + name, allowed)):
            problems.append(f"{where}: '{word}' is not in the cited facts")
        for phrase in hedged_claims(statement["text"], hedges, claims):
            problems.append(f"{where}: {phrase} states a guess as a finding")
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
        out += ["", MEMBERS_HEADING, ""]
        out += [f"- {m['name']}, {m['city']} {m['zip']} · {m['phone']} · score {m['score']}" for m in members]
        out += ["", "These accounts were grouped because they use the same website domain. That happens when one "
                "operator runs several sites, and also when separate businesses trade under the same brand's "
                "website. Common ownership is not established here; check before treating them as one account."]
    else:
        out += ["", CONTACT_HEADING, f"- {smart_title(str(row['address']))}, {row['city']} {row['zip']} · {row['phone']}"]
    out += ["", "## What we don't know"]
    out += [f"- {u}" for u in unknowns] or ["- Nothing flagged."]
    out += ["", "## Facts and sources"]
    out += [render_fact(f) for f in facts]
    out += ["", f"Score breakdown: {row['score_reasons']}", ""]
    return "\n".join(out)


def user_prompt(row: dict, members: list, facts: list) -> str:
    lines = [f"Account: {row['name']}", "", "Facts:"]
    lines += [f"{f['id']}: {f['text']}" for f in facts]
    return "\n".join(lines)


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80]


def main(vertical: str, limit, dry_run: bool, redo_failed: bool) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    cfg = yaml.safe_load(open(vdir / "brief.yaml"))
    system = load_prompt(vdir, "brief_prompt.md")

    scored = pd.read_csv(SCORED_PATH, dtype=str, keep_default_na=False)
    groups = {g: d.to_dict("records") for g, d in scored.groupby("account_group", sort=False)}
    leads = [m[0] for m in groups.values() if m[0]["tier"] in cfg["tiers"]]

    index = pd.read_csv(INDEX_PATH, dtype=str, keep_default_na=False) if INDEX_PATH.exists() else pd.DataFrame(columns=INDEX_COLS)
    from src.current import current_briefs  # here, not at the top: src.current imports this module

    current, stale = current_briefs(index, scored, cfg, BRIEFS_DIR)
    keep = current["check_status"].isin(["passed"] if redo_failed else ["passed", "failed"])
    done = set(current.loc[keep, "account_group"])
    todo = [r for r in leads if r["account_group"] not in done]
    if limit:
        todo = todo[:limit]
    print(f"[brief] {len(leads)} groups in tiers {cfg['tiers']} | {len(leads) - len([r for r in leads if r['account_group'] not in done])} already written | "
          f"{len(stale)} out of date ({', '.join(sorted(set(stale.values()))) or 'none'}) | {len(todo)} to write")

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
            brief, usage, model = generate_json(client, cfg, system, prompt, BRIEF_SCHEMA)
        except Exception as exc:
            return dict(entry, check_status="error", check_notes=f"{type(exc).__name__}: {exc}"[:300])
        problems = source_check(brief, facts, row["name"], cfg.get("allowed_words", []),
                                cfg.get("hedges", []), cfg.get("claim_words", []))
        path = BRIEFS_DIR / f"{int(row['group_rank']):04d}-{slug(row['name'])}.md"
        path.write_text(render(row, members, brief, facts, unknowns, problems))
        return dict(entry, file=path.name, model=model, check_status="failed" if problems else "passed",
                    check_notes=" | ".join(problems), input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens, cost_usd=cost_usd(usage, cfg["price_per_mtok"]))

    if dry_run:
        for result in map(work, todo[:limit or 2]):
            print(f"\n--- {result['name']} ({result['facts']} facts) ---\n{result['_prompt']}\nUnknowns: {result['_unknowns']}")
        return
    if not todo:
        return

    client = make_client()
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
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--limit", type=int, default=None, help="Write only the first N briefs")
    parser.add_argument("--dry-run", action="store_true", help="Print the facts and prompt; call nothing")
    parser.add_argument("--redo-failed", action="store_true", help="Regenerate briefs that failed the source check")
    args = parser.parse_args()
    main(args.vertical, args.limit, args.dry_run, args.redo_failed)
