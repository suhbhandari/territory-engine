#!/usr/bin/env python3
"""
leak_test.py
Searches everything that gets published (site/ and outputs/public/) for any real
identifier held in the private data (outputs/raw/): every account's name, street
address, phone number, website, domain, careers-page URL and ID, plus the IDs of
listings matched during backfill.

Unlike the check inside anonymize.py, which looks for each account's identifiers in
that account's own record, this looks for every account's identifiers in every
published file, so a name that leaks into another account's text is caught too.

A name made only of common words is skipped: a word used in many account names, or a
place name from the data or the metro config, does not identify anyone on its own
(the same rule anonymize.py uses). The count of skipped names is printed.

A person can allow one ordinary phrase that happens to contain an account's name, for
example a name that is also a category word, in outputs/raw/leak_allowlist.csv with the
columns name, allowed_phrase and reason. Only that exact phrase, in the case written, is
blanked out before that one name is searched, so the name on its own, or in a different
case, still fails, and every other name is searched in the unmasked text. The phrase must
contain the name plus at least one more word, and the name must be an account name.
The test prints how many occurrences were masked, never the names.

Exit code 0 means zero leaks; 1 means at least one, listed by kind and file.

Usage:
  python3 scripts/leak_test.py [--root PATH]
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

ROOT = Path(__file__).parent.parent
GENERIC_NAME_SHARE = 8
_LEGAL_TAIL = re.compile(r"(?:[,\s]+(?:llc|inc|corp|corporation|ltd|co|company|lp|llp|pllc)\b\.?)+\s*$", re.I)
_PHONE = re.compile(r"(?<!\d)\(?(\d{3})\)?[\s.-]?(\d{3})[\s.-]?(\d{4})(?!\d)")
_ID = re.compile(r"(?<![\w])(\d{10}|ChIJ[\w-]{10,})(?![\w])")


def _read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False) if path.exists() else pd.DataFrame()


def _tokens(text: str) -> list:
    return [t for t in re.findall(r"[a-z0-9']+", text.lower()) if len(t) >= 3]


def _domain(url: str) -> str:
    url = url.strip().lower()
    if not url:
        return ""
    netloc = urlparse(url if "//" in url else "//" + url).netloc
    return netloc[4:] if netloc.startswith("www.") else netloc


def _url_body(url: str) -> str:
    return re.sub(r"^https?://(www\.)?", "", url.strip().lower()).rstrip("/")


def published_files(root: Path) -> dict:
    files = [p for d in ("site", "outputs/public") for p in (root / d).rglob("*") if p.is_file()]
    return {str(p.relative_to(root)): p.read_text(errors="ignore") for p in sorted(files)}


def _phrase_pattern(phrase: str):
    return re.compile(r"(?<![A-Za-z0-9'])" + re.escape(phrase) + r"(?![A-Za-z0-9'])")


def load_allowlist(raw: Path, names: set) -> dict:
    """Reviewed phrases that may appear in published text: {name: [phrase, ...]}."""
    table = _read(raw / "leak_allowlist.csv")
    allowed = {}
    for _, row in table.iterrows():
        name, phrase = row["name"].strip().lower(), row["allowed_phrase"].strip()
        if name not in names:
            raise SystemExit(f"leak_allowlist.csv: '{name}' is not an account name this test checks")
        if not _phrase_pattern(name).search(phrase.lower()) or len(_tokens(phrase)) <= len(_tokens(name)):
            raise SystemExit(f"leak_allowlist.csv: the phrase for '{name}' must contain the name plus at least one more word")
        allowed.setdefault(name, []).append(phrase)
    return allowed


def identifiers(root: Path) -> dict:
    raw = root / "outputs" / "raw"
    accounts = _read(raw / "accounts_raw.csv")
    signals = _read(raw / "signals_raw.csv")
    cache = _read(raw / "backfill_cache.csv")
    if accounts.empty:
        raise SystemExit(f"no account file at {raw / 'accounts_raw.csv'}; nothing to test against")

    name_counts = Counter(t for n in accounts["name"] for t in set(_tokens(n)))
    generic = {t for t, n in name_counts.items() if n >= GENERIC_NAME_SHARE}
    places = set(_tokens(" ".join(accounts["city"].unique()) + " " + " ".join(accounts["state"].unique())))

    names, skipped = set(), set()
    for name in accounts["name"]:
        for variant in {name.strip(), _LEGAL_TAIL.sub("", name).strip(" ,.")}:
            words = _tokens(variant)
            if not words or len(variant) < 4:
                continue
            (skipped if all(w in generic or w in places for w in words) else names).add(variant.lower())

    # Names a signal found for an account in another table (for example a licence record)
    # identify it just as its own name does.
    for col in [c for c in signals.columns if c.endswith("_names")]:
        for value in signals[col]:
            for name in filter(None, (v.strip() for v in value.split(";"))):
                words = _tokens(name)
                if len(name) >= 4 and words and not all(w in generic or w in places for w in words):
                    names.add(name.lower())

    urls = set(accounts["website"]) | set(signals.get("jobs_source_url", []))
    return {
        "names": names,
        "allowed_phrases": load_allowlist(raw, names),
        "skipped_generic_names": skipped,
        "addresses": {a.lower() for a in accounts["address"] if len(a) >= 6},
        "phones": {d for d in (re.sub(r"\D", "", p)[-10:] for p in accounts["phone"]) if len(d) == 10},
        "urls": {u for u in (_url_body(x) for x in urls) if len(u) >= 5},
        "domains": {d for d in (_domain(x) for x in urls) if len(d) >= 5},
        "ids": (set(accounts["entity_id"]) | set(cache.get("matched_id", []))) - {""},
    }


def find_leaks(root: Path) -> tuple:
    ids = identifiers(root)
    texts = published_files(root)
    hits = []
    for f, text in texts.items():
        lowered = text.lower()
        for kind in ("names", "addresses"):
            for value in ids[kind]:
                haystack = lowered
                if kind == "names" and value in ids["allowed_phrases"]:
                    masked = text
                    for phrase in ids["allowed_phrases"][value]:
                        masked = _phrase_pattern(phrase).sub(" ", masked)
                    haystack = masked.lower()
                if value in haystack and re.search(r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])", haystack):
                    hits.append((kind, value, f))
        for kind in ("urls", "domains"):
            hits += [(kind, v, f) for v in ids[kind] if v in lowered]
        found_phones = {"".join(m.groups()) for m in _PHONE.finditer(text)}
        hits += [("phones", p, f) for p in found_phones & ids["phones"]]
        found_ids = {m.group(1) for m in _ID.finditer(text)}
        hits += [("ids", i, f) for i in found_ids & ids["ids"]]
    return hits, ids, texts


def main(root: Path) -> int:
    hits, ids, texts = find_leaks(root)
    print("=== leak test ===")
    print(f"Published files scanned: {len(texts)}")
    print("Identifiers checked: " + ", ".join(f"{k} {len(v)}" for k, v in ids.items() if k not in ("skipped_generic_names", "allowed_phrases")))
    print(f"Names skipped as made only of common or place words: {len(ids['skipped_generic_names'])}")
    masked = sum(len(_phrase_pattern(ph).findall(t)) for ph_list in ids["allowed_phrases"].values() for ph in ph_list for t in texts.values())
    print(f"Reviewed phrases masked: {masked} occurrences from {sum(len(v) for v in ids['allowed_phrases'].values())} allowlist rows")
    if hits:
        print(f"FAIL: {len(hits)} leak(s)")
        for kind, _, f in sorted(set(hits))[:30]:
            print(f"  {kind} in {f}")  # the value itself is not printed, so the log stays shareable
        return 1
    print("PASS: 0 leaks")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    sys.exit(main(parser.parse_args().root))
