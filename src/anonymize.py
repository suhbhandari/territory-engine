"""
Phase 7: Public Dataset
Builds the anonymized dataset the public site and report card read. Real account names,
addresses, phone numbers, websites and registry IDs never leave outputs/raw/.

Usage:
  python3 src/anonymize.py [--vertical <name>] [--metro config/metro/<name>.yaml]

Design:
  - Each account group gets an alias ("Account 0001") in rank order; its locations become
    "Account 0001-2" and so on. Structured fields are copied selectively: nothing that
    identifies the business is included, and zip codes are cut to three digits
  - Free text (score reasons, briefs, outreach drafts) is scrubbed: the group's names, the
    distinctive words in those names, its domain, address, phone and IDs are replaced, then
    generic patterns catch any URL, phone number, street address, long ID or zip code
  - "Distinctive" is computed from the data: a word that appears in only a few account
    names identifies the account, while a word shared by many names, or used in the
    generated text of many different groups (ordinary language like "open"), does not
  - A leak check then searches every published text for that group's own identifiers.
    Any hit fails the build, so a scrub gap cannot ship silently
  - Open-role counts are published as ranges (1-4, 5-19, 20-49, 50-99, 100+), in the
    open_roles field and in the text, because an exact count plus a city points to one employer
  - Limits: this removes names and contact details and blurs counts. It does not make an
    account impossible to re-identify from its combination of facts (hiring system, city,
    number of locations, years registered)
"""

import argparse
import json
import re
import sys
import yaml
import pandas as pd
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.brief import parse_fact_line  # noqa: E402
from src.current import current_briefs, current_sequences  # noqa: E402
from src.settings import DEFAULT_METRO, DEFAULT_VERTICAL  # noqa: E402

RAW = ROOT / "outputs" / "raw"
PUBLIC = ROOT / "outputs" / "public"

GENERIC_NAME_SHARE = 8  # a name word used by at least this many accounts is not identifying
GENERIC_TEXT_SHARE = 10  # nor is a word that appears in the generated text of this many groups
_STREET_TYPES = (r"(?:st|street|ave|avenue|blvd|boulevard|rd|road|pkwy|parkway|pl|place|hwy|highway|"
                 r"dr|drive|ln|lane|tpke|turnpike|ct|court|plz|plaza|ter|terrace|expy|expressway|way|broadway)")
_PATTERNS = [
    (re.compile(r"https?://\S+"), "[website]"),
    (re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,6}\b(?:/\S*)?", re.I), "[website]"),
    (re.compile(r"\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]\d{4}\b"), "[phone]"),
    (re.compile(r"\bChIJ[\w-]{10,}"), "[id]"),
    (re.compile(r"\b\d{10}\b"), "[id]"),
    (re.compile(rf"\b\d[\d-]*\s+(?:[\w.'&-]+\s+){{0,4}}?{_STREET_TYPES}\b\.?(?:[,\s]+(?:ste|suite|fl|floor|apt|unit|rm|room|#)\.?\s*[\w-]+)?", re.I), "[address]"),
    # Street names without a number. Case-sensitive on the name so ordinary words are not eaten.
    (re.compile(rf"\b(?:[NSEW]\.?\s+)?(?:\d+(?i:st|nd|rd|th)|[A-Z][\w'-]+)(?:\s[A-Z][\w'-]+)?\s(?i:{_STREET_TYPES})\b\.?"), "[street]"),
    (re.compile(r"\b(\d{3})\d{2}(?:-\d{4})?\b"), r"\1xx"),
]
_COUNT_BANDS = [(100, "100+"), (50, "50-99"), (20, "20-49"), (5, "5-19"), (1, "1-4"), (0, "0")]
# A number followed within a few words by a word for job openings, or a total "across all locations".
_ROLE_COUNT = re.compile(r"\b\d[\d,]*(?=(?:\s+[\w/'-]+){0,3}?\s+(?:roles?|postings?|openings?|positions?|jobs?)\b"
                         r"|\s+across\s+all\s+locations)", re.I)


def band(count: str) -> str:
    """'161' -> '100+'; blank stays blank (unknown is not zero)."""
    if not str(count).strip():
        return ""
    n = int(float(str(count).replace(",", "")))
    return next(label for floor, label in _COUNT_BANDS if n >= floor)


def band_counts(text: str) -> str:
    return _ROLE_COUNT.sub(lambda m: band(m.group(0)), text)


_LEGAL = re.compile(r"(\[?Account \d{4}(?:-\d+)?\]?)(?:[,\s]+(?:llc|inc|corp|corporation|ltd|co|company|lp|llp|pllc)\b\.?)+", re.I)


_LEGAL_TAIL = re.compile(r"(?:[,\s]+(?:llc|inc|corp|corporation|ltd|co|company|lp|llp|pllc)\b\.?)+\s*$", re.I)


def _tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if len(t) >= 3]


def identifying_words(members: list, generic: set, place_words: set) -> set:
    words = set()
    for m in members:
        words.update(t for t in _tokens(m["name"]) if t not in generic and t not in place_words)
        stem = m["website_domain"].split(".")[0]
        if len(stem) >= 4 and stem not in generic:
            words.add(stem)
    return words


def short_name(name: str) -> str:
    """The name as people say it: legal suffixes and trailing punctuation dropped."""
    return _LEGAL_TAIL.sub("", name).strip(" ,.")


def scrub(text: str, alias: str, members: list, words: set) -> str:
    if not text:
        return text
    for m in sorted(members, key=lambda m: -len(m["name"])):
        text = re.sub(re.escape(m["name"]), alias, text, flags=re.I)
        if len(short_name(m["name"]).split()) >= 2:
            text = re.sub(re.escape(short_name(m["name"])), alias, text, flags=re.I)
        if m["address"]:
            text = re.sub(re.escape(m["address"]), "[address]", text, flags=re.I)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    for word in sorted(words, key=len, reverse=True):
        text = re.sub(_word_pattern(word) + r"(?:'s)?", alias, text, flags=re.I)
    text = re.sub(rf"(?:{re.escape(alias)}[\s,&-]*)+{re.escape(alias)}", alias, text)
    return band_counts(_LEGAL.sub(r"\1", text))


def _word_pattern(word: str) -> str:
    # Long words are matched even inside a longer token (domain stems, possessives).
    return re.escape(word) if len(word) >= 6 else rf"\b{re.escape(word)}\b"


def leaks(text: str, members: list, words: set) -> list:
    lowered = text.lower()
    found = [w for w in words if re.search(_word_pattern(w), lowered)]
    for m in members:
        if len(short_name(m["name"]).split()) >= 2 and short_name(m["name"]).lower() in lowered:
            found.append(f"name '{short_name(m['name'])}'")
        digits = re.sub(r"\D", "", m["phone"])[-7:]
        if len(digits) == 7 and digits in re.sub(r"\D", "", text):
            found.append(f"phone …{digits}")
        if m["entity_id"] and m["entity_id"] in text:
            found.append("entity id")
        if m["website_domain"] and m["website_domain"] in lowered:
            found.append(m["website_domain"])
    return found


def parse_sections(markdown: str) -> dict:
    sections, current = {"_lead": []}, "_lead"
    for line in markdown.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif line.strip() and not line.startswith(("# ", "**Tier", ">")):
            fact = parse_fact_line(line)
            sections[current].append(f"**{fact['id']}** {fact['text']}" if fact else line.lstrip("- ").strip())
    return sections


def main(vertical: str, metro_path: str) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    rubric = yaml.safe_load(open(vdir / "rubric.yaml"))
    glossary = yaml.safe_load(open(vdir / "glossary.yaml"))
    geo = yaml.safe_load(open(ROOT / metro_path))
    seq_cfg = yaml.safe_load(open(vdir / "sequence.yaml"))

    scored = pd.read_csv(RAW / "accounts_scored.csv", dtype=str, keep_default_na=False)
    briefs = pd.read_csv(RAW / "briefs" / "briefs_index.csv", dtype=str, keep_default_na=False)
    touches = pd.read_csv(RAW / "sequences" / "sequences.csv", dtype=str, keep_default_na=False)
    seq_index = pd.read_csv(RAW / "sequences" / "sequences_index.csv", dtype=str, keep_default_na=False)
    facts_cfg = yaml.safe_load(open(vdir / "brief.yaml"))
    # Publish only text that still matches the scored data and passed its checks.
    briefs, _ = current_briefs(briefs, scored, facts_cfg, RAW / "briefs")
    briefs = briefs[briefs["check_status"] == "passed"]
    seq_index, _ = current_sequences(seq_index, touches, scored, seq_cfg, facts_cfg, RAW / "sequences")
    touches = touches[touches["account_group"].isin(seq_index["account_group"])]

    name_counts = Counter(t for name in scored["name"] for t in set(_tokens(name)))
    generic = {t for t, n in name_counts.items() if n >= GENERIC_NAME_SHARE}
    place_words = set(_tokens(" ".join(scored["city"].unique()) + " " + " ".join(geo.get("search_cities", []))))
    place_words.update(_tokens(geo.get("city", "")) + [geo.get("state", "").lower()])

    brief_file = dict(zip(briefs["account_group"], briefs["file"]))
    brief_text = {g: (RAW / "briefs" / f).read_text() for g, f in brief_file.items()}
    touch_text = touches.groupby("account_group").apply(lambda d: " ".join(d["subject"] + " " + d["body"])).to_dict()
    text_counts = Counter()
    for group_key, frame in scored.groupby("account_group", sort=False):
        own = " ".join(frame["score_reasons"]) + " " + " ".join(frame["license_type"])
        # Fact lines quote names and addresses verbatim, so only the written sections count.
        written = brief_text.get(group_key, "").split("## Locations")[0].split("## Contact")[0]
        text_counts.update(set(_tokens(own + " " + written + " " + touch_text.get(group_key, ""))))
    generic |= {t for t, n in text_counts.items() if n >= GENERIC_TEXT_SHARE}
    criteria = list(rubric["criteria"])
    accounts, all_leaks = [], []

    for group_key, frame in scored.groupby("account_group", sort=False):
        members = frame.to_dict("records")
        lead = members[0]
        alias = f"Account {int(lead['group_rank']):04d}"
        words = identifying_words(members, generic, place_words)
        clean = lambda text: scrub(text, alias, members, words)

        record = {
            "id": alias,
            "rank": int(lead["group_rank"]),
            "tier": lead["tier"],
            "score": int(lead["score"]),
            "data_coverage": float(lead["data_coverage"]),
            "city": lead["city"],
            "zip3": lead["zip"][:3],
            "type": lead["license_type"],
            "locations": int(lead["group_size"]),
            "years_registered": lead["npi_age_years"],
            "has_website": lead["website"] != "",
            "hiring_status": lead["jobs_status"],
            "hiring_system": lead["jobs_ats"],
            "open_roles": band(lead["jobs_total"]),
            "points": {c: int(lead[f"pts_{c}"]) for c in criteria},
            "reasons": [clean(r) for r in lead["score_reasons"].split("; ") if r],
        }

        if group_key in brief_file:
            sections = parse_sections(brief_text[group_key])
            record["brief"] = {
                "headline": clean(" ".join(sections["_lead"])),
                "snapshot": [clean(l) for l in sections.get("Snapshot", [])],
                "why_now": [clean(l) for l in sections.get("Why now", [])],
                "opening_angle": clean(" ".join(sections.get("Opening angle", []))),
                "unknowns": [clean(l) for l in sections.get("What we don't know", [])],
                "facts": [clean(l) for l in sections.get("Facts and sources", [])],
            }
        group_touches = touches[(touches["account_group"] == group_key) & (touches["check_status"] == "passed")]
        if len(group_touches):
            record["persona"] = group_touches.iloc[0]["persona"]
            record["sequence"] = [
                {"touch": int(t["touch"]), "channel": t["channel"], "day": int(t["day"]),
                 "subject": clean(t["subject"]), "body": clean(t["body"]), "fact_ids": t["fact_ids"]}
                for t in group_touches.to_dict("records")
            ]

        brief = record.get("brief", {})
        published = record["reasons"] + [v for v in brief.values() if isinstance(v, str)]
        published += [line for v in brief.values() if isinstance(v, list) for line in v]
        published += [t[k] for t in record.get("sequence", []) for k in ("subject", "body")]
        found = leaks("\n".join(published), members, words)
        if found:
            all_leaks.append((alias, sorted(set(found))))
        accounts.append(record)

    if all_leaks:
        print(f"[anonymize] FAILED: identifiers remain in {len(all_leaks)} of {len(accounts)} records. Nothing written.")
        for alias, found in all_leaks[:15]:
            print(f"  {alias}: {', '.join(found[:6])}")
        sys.exit(1)

    data = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "vertical": glossary.get("vertical_name", vertical),
        "metro": geo.get("metro", ""),
        "tiers": rubric["tiers"],
        "criteria": [{"key": k, "label": c.get("label", k), "max_points": c["max_points"], "why": c.get("why", "").strip()[:1].upper() + c.get("why", "").strip()[1:]}
                     for k, c in rubric["criteria"].items()],
        "touches": [{"id": t["id"], "channel": t["channel"], "day": t["day"], "max_words": t["max_words"]} for t in seq_cfg["touches"]],
        "accounts": accounts,
    }
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "site_data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    (PUBLIC / "site_data.js").write_text("window.SITE_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")

    flat = pd.DataFrame([{k: v for k, v in a.items() if k not in ("points", "reasons", "brief", "sequence")} for a in accounts])
    flat.to_csv(PUBLIC / "accounts_public.csv", index=False)
    with_text = sum(1 for a in accounts if "brief" in a)
    print(f"[anonymize] {len(accounts)} account groups published ({with_text} with brief and sequence text); leak check passed")
    print(f"[anonymize] Written → {PUBLIC.relative_to(ROOT)}/site_data.json, site_data.js, accounts_public.csv")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    parser.add_argument("--metro", default=DEFAULT_METRO)
    args = parser.parse_args()
    main(args.vertical, args.metro)
