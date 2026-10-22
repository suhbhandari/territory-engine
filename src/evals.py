"""
Phase 7: Eval Report Card
Measures what the pipeline produced, from its own output files, and states plainly what
has not been measured. Writes the report card and the cost summary to outputs/public/.

Usage:
  python3 src/evals.py [--vertical <name>]

Design:
  - Every measurement is computed from files on disk. The only text typed by hand is in the
    vertical's evals.yaml (what the checks cover, what is not measured, cost estimates), and
    the card labels it as such
  - No letter grades: without outcome data or human labels a grade would be invented.
    Each line is a measurement, and the "not measured" list is part of the card
  - Calls no external service
"""

import argparse
import json
import re
import sys
import yaml
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.paths import RAW, PUBLIC  # noqa: E402
from src.current import current_briefs, current_sequences  # noqa: E402
from src.settings import DEFAULT_VERTICAL  # noqa: E402



def whole(value):
    """int for a count or average; None when there is nothing to measure (shown as n/a)."""
    return None if pd.isna(value) else int(value)


def pct(part, whole) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def data_dates(scored: pd.DataFrame) -> dict:
    """When the data was collected, as opposed to when this report was built."""
    dates = {}
    for key, col in (("discovered", "discovered_at"), ("signals_checked", "signals_fetched_at")):
        values = scored[col].str[:10].replace("", pd.NA).dropna() if col in scored else pd.Series(dtype=str)
        dates[key] = {"first": values.min(), "last": values.max()} if len(values) else None
    return dates


def first_attempt_summary(log: dict) -> dict:
    """Totals of first-attempt check results per step, from the hand-kept log of run results.

    A first attempt is a draft as first written, before any re-run of a failed one. The log is
    typed from run output (outputs/raw/first_pass_log.json), because the draft indexes keep
    only the final result for each group.
    """
    steps = {}
    for run in log.get("runs", []):
        # Keyed by step AND prompt: a pass rate only means something next to the prompt
        # that produced it, and a later prompt is often judged by stricter checks.
        key = (run["step"], run.get("prompt", "unrecorded"))
        t = steps.setdefault(key, {"step": run["step"], "prompt": key[1], "written": 0, "passed": 0,
                                   "failed": 0, "failure_types": {}})
        for field in ("written", "passed", "failed"):
            t[field] += int(run[field])
        for kind, count in run.get("failure_types", {}).items():
            t["failure_types"][kind] = t["failure_types"].get(kind, 0) + int(count)
    for t in steps.values():
        t["passed_pct"] = pct(t["passed"], t["written"])
    steps = list(steps.values())
    retries = {}
    for run in log.get("retries", []):
        t = retries.setdefault(run["step"], {"redone": 0, "passed": 0})
        t["redone"] += int(run["redone"])
        t["passed"] += int(run["passed"])
    return {"steps": steps, "retries": retries}


def refresh_summary(scored: pd.DataFrame, briefs_all: pd.DataFrame, seqs_all: pd.DataFrame) -> dict:
    """What changed since the previous saved run: tier moves, trigger rows by type, and the
    drafts written in this run, split into rewrites and groups new to the drafted tiers."""
    from src.triggers import latest_snapshot  # here, not at the top: only this section needs it
    trig_path = RAW / "triggers.csv"
    if not trig_path.exists():
        return None
    try:
        prev_dir = latest_snapshot(set(scored["signals_fetched_at"].str[:10]))
    except SystemExit:
        return None
    prev = pd.read_csv(prev_dir / "accounts_scored.csv", dtype=str, keep_default_na=False)
    trig = pd.read_csv(trig_path, dtype=str, keep_default_na=False)
    both = prev[["entity_id", "tier"]].merge(scored[["entity_id", "tier"]], on="entity_id", suffixes=("_before", "_after"))
    moved = both[both["tier_before"] != both["tier_after"]]
    drafted = sorted(set(briefs_all["tier"]))
    was_drafted = set(prev.loc[prev["tier"].isin(drafted), "account_group"])
    since = data_dates(scored)["signals_checked"]["first"]
    written = {}
    for label, index in (("briefs", briefs_all), ("sequences", seqs_all)):
        new = index[index["generated_at"].str[:10] >= since]
        rewrites = new["account_group"].isin(was_drafted)
        written[label] = {"written": len(new), "rewritten": int(rewrites.sum()), "new_groups": int((~rewrites).sum()),
                          "cost_usd": round(pd.to_numeric(new["cost_usd"], errors="coerce").sum(), 2)}
    return {
        "previous_run": prev_dir.name,
        "previous_signals": data_dates(prev)["signals_checked"],
        "accounts_compared": len(both),
        "accounts_new": int((~scored["entity_id"].isin(prev["entity_id"])).sum()),
        "accounts_gone": int((~prev["entity_id"].isin(scored["entity_id"])).sum()),
        "tier_changes": len(moved),
        "tier_changes_by_direction": (moved["tier_before"] + " to " + moved["tier_after"]).value_counts().to_dict(),
        "trigger_rows": len(trig),
        "trigger_rows_by_type": trig["what"].value_counts().to_dict(),
        "accounts_with_trigger": int(trig["entity_id"].nunique()),
        "drafted_tiers": drafted,
        "accounts_in_drafted_tiers_with_trigger": int(trig.loc[trig["tier"].isin(drafted), "entity_id"].nunique()),
        "drafts": written,
    }


def _date_range(d) -> str:
    if not d:
        return "not recorded"
    return d["first"] if d["first"] == d["last"] else f"{d['first']} to {d['last']}"


def main(vertical: str) -> None:
    vdir = ROOT / "config" / "verticals" / vertical
    rubric = yaml.safe_load(open(vdir / "rubric.yaml"))
    seq_cfg = yaml.safe_load(open(vdir / "sequence.yaml"))
    evals_cfg = yaml.safe_load(open(vdir / "evals.yaml"))

    scored = pd.read_csv(RAW / "accounts_scored.csv", dtype=str, keep_default_na=False)
    signals = pd.read_csv(RAW / "signals_raw.csv", dtype=str, keep_default_na=False)
    briefs = pd.read_csv(RAW / "briefs" / "briefs_index.csv", dtype=str, keep_default_na=False)
    seqs = pd.read_csv(RAW / "sequences" / "sequences_index.csv", dtype=str, keep_default_na=False)
    touches = pd.read_csv(RAW / "sequences" / "sequences.csv", dtype=str, keep_default_na=False)
    excluded_path = RAW / "accounts_excluded.csv"
    excluded = pd.read_csv(excluded_path, dtype=str, keep_default_na=False) if excluded_path.exists() else pd.DataFrame(columns=["excluded_because"])
    summary_path = RAW / "discover_summary.json"
    discover_summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    facts_cfg = yaml.safe_load(open(vdir / "brief.yaml"))
    # Measure only what is current: accounts still in the list, text that still matches the data.
    signals = signals[signals["entity_id"].isin(scored["entity_id"])]
    # Costs cover everything the index logs as written, current or not: that is what was spent.
    briefs_all, seqs_all = briefs, seqs
    briefs, stale_briefs = current_briefs(briefs, scored, facts_cfg, RAW / "briefs")
    seqs, stale_seqs = current_sequences(seqs, touches, scored, seq_cfg, facts_cfg, RAW / "sequences")
    touches = touches[touches["account_group"].isin(seqs["account_group"])]
    n = len(scored)
    leads = scored[scored["rank_in_group"] == "1"]

    discovery = {
        "accounts": n,
        "groups": len(leads),
        "by_source": scored["source"].value_counts().to_dict(),
        "with_website_pct": pct((scored["website"] != "").sum(), n),
        "with_phone_pct": pct((scored["phone"] != "").sum(), n),
        "excluded": {**({"outside territory (dropped by discover)": discover_summary["dropped_outside_territory"]}
                         if discover_summary.get("dropped_outside_territory") else {}),
                      **excluded["excluded_because"].str.split(":").str[0].value_counts().to_dict()},
        "rows_merged_as_duplicates": discover_summary.get("rows_merged"),
        "rows_fetched_by_source": discover_summary.get("fetched_by_source", {}),
    }

    error_cols = [c for c in signals.columns if c.endswith("_error")]
    data_cols = [c for c in signals.columns if c not in error_cols and c not in ("entity_id", "signals_fetched_at")
                 and not c.endswith("_checked_website")]
    signal_stats = {
        "accounts_enriched": len(signals),
        "errors": {c[:-6]: int((signals[c] != "").sum()) for c in error_cols},
        "filled_pct": {c: pct((signals[c] != "").sum(), len(signals)) for c in data_cols},
        "status_breakdown": {c: signals[c].value_counts().to_dict() for c in data_cols if c.endswith("_status")},
    }

    score = pd.to_numeric(scored["score"])
    coverage = pd.to_numeric(scored["data_coverage"])
    scoring = {
        "tiers": [{"tier": t["name"], "min_score": t["min_score"],
                   "accounts": int((scored["tier"] == t["name"]).sum()),
                   "groups": int((leads["tier"] == t["name"]).sum()),
                   "avg_data_coverage_pct": round(100 * coverage[scored["tier"] == t["name"]].mean(), 1)}
                  for t in rubric["tiers"]],
        "avg_data_coverage_pct": round(100 * coverage.mean(), 1),
        "median_score": float(score.median()),
        "criteria": [{"key": k, "label": c.get("label", k), "max_points": c["max_points"],
                      "avg_points": round(pd.to_numeric(scored[f"pts_{k}"]).mean(), 1),
                      "accounts_scoring_above_zero_pct": pct((pd.to_numeric(scored[f"pts_{k}"]) > 0).sum(), n)}
                     for k, c in rubric["criteria"].items()],
        "weights_fitted_to_outcomes": False,
    }

    statements, facts_cited, facts_total = 0, 0, 0
    for name in briefs.loc[briefs["check_status"] == "passed", "file"]:
        text = (RAW / "briefs" / name).read_text()
        body = text.split("## What we don't know")[0]
        cited = re.findall(r"\[(F\d+(?:, F\d+)*)\]", body)
        statements += len(cited)
        facts_cited += len({f for group in cited for f in group.split(", ")})
        facts_total += len(re.findall(r"^- \*\*F\d+\*\*", text, flags=re.M))
    brief_cost = pd.to_numeric(briefs_all["cost_usd"], errors="coerce")
    brief_stats = {
        "written": len(briefs),
        "out_of_date": len(stale_briefs),
        "out_of_date_reasons": pd.Series(list(stale_briefs.values()), dtype=object).value_counts().to_dict(),
        "passed_source_check_pct": pct((briefs["check_status"] == "passed").sum(), len(briefs)),
        "statements": statements,
        "statements_per_brief": round(statements / max(len(briefs), 1), 1),
        "facts_per_brief": round(facts_total / max(len(briefs), 1), 1),
        "facts_used_pct": pct(facts_cited, facts_total),
        "avg_cost_usd": round(brief_cost.mean(), 4),
        "total_cost_usd": round(brief_cost.sum(), 2),
        "cost_items": int(brief_cost.notna().sum()),
        "avg_input_tokens": whole(pd.to_numeric(briefs_all["input_tokens"], errors="coerce").mean()),
        "avg_output_tokens": whole(pd.to_numeric(briefs_all["output_tokens"], errors="coerce").mean()),
        "model": briefs_all["model"].mode().iat[0],
    }

    limits = {i + 1: t["max_words"] for i, t in enumerate(seq_cfg["touches"])}
    words = pd.to_numeric(touches["word_count"])
    last_question = touches["body"].str.findall(r"[^.?!\n]*\?").str[-1].fillna("").str.strip().str.lower()
    first_touch = touches["touch"] == "1"
    seq_cost = pd.to_numeric(seqs_all["cost_usd"], errors="coerce")
    sequence_stats = {
        "written": len(seqs),
        "out_of_date": len(stale_seqs),
        "out_of_date_reasons": pd.Series(list(stale_seqs.values()), dtype=object).value_counts().to_dict(),
        "touches": len(touches),
        "passed_checks_pct": pct((seqs["check_status"] == "passed").sum(), len(seqs)),
        "touch_lengths": [{"touch": t, "limit_words": limit,
                           "avg_words": round(words[touches["touch"] == str(t)].mean(), 1),
                           "max_words": whole(words[touches["touch"] == str(t)].max())}
                          for t, limit in limits.items()],
        "distinct_first_email_questions_pct": pct(last_question[first_touch].nunique(), int(first_touch.sum())),
        "most_repeated_first_email_question_count": whole(last_question[first_touch].value_counts().max()),
        "personas": seqs["persona"].value_counts().to_dict(),
        "avg_cost_usd": round(seq_cost.mean(), 4),
        "total_cost_usd": round(seq_cost.sum(), 2),
        "cost_items": int(seq_cost.notna().sum()),
        "avg_input_tokens": whole(pd.to_numeric(seqs_all["input_tokens"], errors="coerce").mean()),
        "avg_output_tokens": whole(pd.to_numeric(seqs_all["output_tokens"], errors="coerce").mean()),
        "model": seqs_all["model"].mode().iat[0],
    }

    log_path = RAW / "first_pass_log.json"
    if log_path.exists():
        log = json.loads(log_path.read_text())
        first_attempts = first_attempt_summary(log)
        first_attempts["quality_before_after"] = log.get("quality_before_after")
    else:
        first_attempts = None

    # CRM pushes that wrote, from push_hubspot's log. Counts only; the log stays private.
    push_log = RAW / "hubspot_push_log.json"
    crm_pushes = [{k: r.get(k) for k in ("at", "source", "accounts", "created", "updated", "unchanged")}
                  for r in json.loads(push_log.read_text()) if r.get("mode") == "write"] if push_log.exists() else []

    refresh = refresh_summary(scored, briefs_all, seqs_all)

    card = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "data_as_of": data_dates(scored),
        "discovery": discovery,
        "signals": signal_stats,
        "scoring": scoring,
        "briefs": brief_stats,
        "sequences": sequence_stats,
        "first_attempts": first_attempts,
        "crm_pushes": crm_pushes,
        "refresh": refresh,
        "checks_cover": evals_cfg["checks_cover"],
        "not_measured": evals_cfg["not_measured"],
        "other_costs": evals_cfg.get("other_costs", []),
    }
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "report_card.json").write_text(json.dumps(card, indent=2))
    (PUBLIC / "report_card.js").write_text("window.REPORT_CARD = " + json.dumps(card) + ";\n")
    (PUBLIC / "report_card.md").write_text(render_card(card))
    (PUBLIC / "costs.md").write_text(render_costs(card))
    print(f"[evals] Written → {PUBLIC.relative_to(ROOT)}/report_card.json, report_card.js, report_card.md, costs.md")
    print(f"[evals] briefs passed {brief_stats['passed_source_check_pct']}% | sequences passed {sequence_stats['passed_checks_pct']}% | "
          f"avg data coverage {scoring['avg_data_coverage_pct']}% | {len(card['not_measured'])} things not measured")


def render_card(c: dict) -> str:
    d, s, b, q = c["discovery"], c["scoring"], c["briefs"], c["sequences"]
    out = [f"# Report card", "", f"Built {c['generated_at']} from the pipeline's own output files. "
           f"Signals collected: {_date_range(c['data_as_of']['signals_checked'])}. "
           f"Accounts discovered: {_date_range(c['data_as_of']['discovered'])}.", "",
           "Measurements only: no grades, because no outcome data or human labels exist yet. "
           "The last two sections are written by hand in the vertical's evals.yaml.", "",
           "## Discovery", "",
           f"- {d['accounts']} accounts in {d['groups']} groups (accounts sharing a website count as one group).",
           f"- By source: " + ", ".join(f"{k}: {v}" for k, v in d["by_source"].items()) + ".",
           f"- {d['with_website_pct']}% have a website; {d['with_phone_pct']}% have a phone number.",
           "- Left out before scoring: " + (", ".join(f"{k}: {v}" for k, v in d["excluded"].items()) or "none") + ".",
           f"- Rows fetched by source: " + (", ".join(f"{k}: {v}" for k, v in d["rows_fetched_by_source"].items()) or "not recorded")
           + f"; {d['rows_merged_as_duplicates'] if d['rows_merged_as_duplicates'] is not None else 'not recorded'} rows merged as duplicates.", "",
           "## Signals", "",
           f"- {c['signals']['accounts_enriched']} accounts enriched. Signal errors: "
           + ", ".join(f"{k}: {v}" for k, v in c["signals"]["errors"].items()) + ".",
           "", "| Signal column | Accounts with a value |", "|---|---|"]
    out += [f"| `{k}` | {v}% |" for k, v in c["signals"]["filled_pct"].items()]
    for col, breakdown in c["signals"]["status_breakdown"].items():
        out += ["", f"`{col}` breakdown:", "", "| Status | Accounts |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in breakdown.items()]
    out += ["", "## Scoring", "", "The rubric weights are a hypothesis. They have not been fitted to meetings booked or deals won.", "",
            "| Tier | Minimum score | Accounts | Groups | Average data coverage |", "|---|---|---|---|---|"]
    out += [f"| {t['tier']} | {t['min_score']} | {t['accounts']} | {t['groups']} | {t['avg_data_coverage_pct']}% |" for t in s["tiers"]]
    out += ["", "Data coverage is the share of the rubric judged on real data. A low score with low coverage means "
            "\"could not find out\", not \"poor fit\".", "",
            "| Criterion | Max points | Average points | Accounts scoring above zero |", "|---|---|---|---|"]
    out += [f"| {k['label']} | {k['max_points']} | {k['avg_points']} | {k['accounts_scoring_above_zero_pct']}% |" for k in s["criteria"]]
    out += ["", "## Briefs", "",
            f"- {b['written']} briefs written; {b['passed_source_check_pct']}% pass the source check. "
            f"{b['out_of_date']} more are out of date and are not counted or published until rewritten"
            + (" (" + ", ".join(f"{k}: {v}" for k, v in b["out_of_date_reasons"].items()) + ")." if b["out_of_date"] else "."),
            f"- {b['statements']} statements, {b['statements_per_brief']} per brief, each citing at least one numbered fact.",
            f"- {b['facts_per_brief']} facts available per brief; {b['facts_used_pct']}% of available facts were cited.", "",
            "## Sequences", "",
            f"- {q['written']} sequences ({q['touches']} touches); {q['passed_checks_pct']}% pass their checks. "
            f"{q['out_of_date']} more are out of date and are not counted or published until rewritten"
            + (" (" + ", ".join(f"{k}: {v}" for k, v in q["out_of_date_reasons"].items()) + ")." if q["out_of_date"] else "."),
            f"- First-email closing questions: {q['distinct_first_email_questions_pct']}% are distinct; "
            f"the most repeated one appears {q['most_repeated_first_email_question_count']} times.",
            "- Written for: " + ", ".join(f"{k} ({v})" for k, v in q["personas"].items()) + ".", "",
            "| Touch | Word limit | Average words | Longest |", "|---|---|---|---|"]
    out += [f"| {t['touch']} | {t['limit_words']} | {t['avg_words']} | {t['max_words']} |" for t in q["touch_lengths"]]
    fa = c.get("first_attempts")
    if fa and fa["steps"]:
        out += ["", "## First-attempt results, by prompt version", "",
                "A draft as it was first written, before any re-run of one that failed. Taken from the run logs and kept "
                "by hand in a private file, because the draft files keep only the final result. The pass rates earlier in "
                "this card are after failed drafts were re-run, so they are 100%.", "",
                "A later prompt version is judged by whatever checks existed when it ran, and checks were added along the "
                "way, so the rates below are not a clean comparison between prompt versions.", "",
                "| Step | Prompt version | First attempts | Passed first time | Pass rate | What failed |",
                "|---|---|---|---|---|---|"]
        labels = {"brief": "Briefs", "sequence": "Sequences"}
        for t in sorted(fa["steps"], key=lambda x: (x["step"], x["prompt"])):
            why = ", ".join(f"{k} ({v})" for k, v in t["failure_types"].items()) or "nothing"
            out += [f"| {labels.get(t['step'], t['step'])} | {t['prompt']} | {t['written']} | {t['passed']} | {t['passed_pct']}% | {why} |"]
        out += [""]
        for step, label in labels.items():
            r = fa["retries"].get(step)
            if r:
                out += [f"- {label}: {r['redone']} re-run attempts, {r['passed']} passed. A draft that failed twice is counted twice."]
    ba = (c.get("first_attempts") or {}).get("quality_before_after")
    if ba:
        out += ["", "## What changed when a check was added", "",
                "Each row is the same measurement, run over the published drafts before and after a check and a prompt "
                "rule were added for it on 2026-10-13. The checks were written after a blind grading of 15 briefs by a "
                "model that had not seen the pipeline; the problems it found were not caught by any check at the time.", "",
                "| Measurement | Before | After |", "|---|---|---|"]
        out += [f"| {k} | {v['before']} | {v['after']} |" for k, v in ba.items()
                if isinstance(v, dict) and "before" in v]
        if ba.get("note"):
            out += ["", ba["note"]]
    r = c.get("refresh")
    if r:
        out += ["", "## Week over week", "",
                f"This run compared with the saved run `{r['previous_run']}`. Signals before: "
                f"{_date_range(r['previous_signals'])}; after: {_date_range(c['data_as_of']['signals_checked'])}. "
                f"{r['accounts_compared']} accounts are in both runs, {r['accounts_new']} are new and {r['accounts_gone']} are gone.", "",
                f"- {r['tier_changes']} of {r['accounts_compared']} accounts changed tier: "
                + ", ".join(f"{k}: {v}" for k, v in r["tier_changes_by_direction"].items()) + ".",
                f"- {r['trigger_rows']} trigger events on {r['accounts_with_trigger']} accounts; "
                f"{r['accounts_in_drafted_tiers_with_trigger']} of those accounts are now in tiers "
                + " or ".join(r["drafted_tiers"]) + ".", "",
                "| Trigger | Events |", "|---|---|"]
        out += [f"| {k} | {v} |" for k, v in r["trigger_rows_by_type"].items()]
        out += [""] + [f"- {k.capitalize()} written in this run: {v['written']} ({v['rewritten']} rewritten because "
                       f"their facts changed, {v['new_groups']} for groups new to tiers {' and '.join(r['drafted_tiers'])}); "
                       f"${v['cost_usd']:.2f}. The rest were kept as they were."
                       for k, v in r["drafts"].items()]
        out += ["", "Whether these changes are worth a rep acting on has not been judged by a rep."]
    if c.get("crm_pushes"):
        out += ["", "## CRM push (HubSpot)", "",
                "Each run that wrote to HubSpot, from the push log. Unchanged accounts are not sent, so a "
                "second identical run should show 0 created and 0 updated.", "",
                "| Run (UTC) | Source | Accounts | Created | Updated | Unchanged |", "|---|---|---|---|---|---|"]
        out += [f"| {r['at']} | {r['source']} | {r['accounts']} | {r['created']} | {r['updated']} | {r['unchanged']} |"
                for r in c["crm_pushes"]]
    out += ["", "## What the automated checks cover (written by hand)", ""] + [f"- {x}" for x in c["checks_cover"]]
    out += ["", "## Not measured (written by hand)", ""] + [f"- {x}" for x in c["not_measured"]]
    return "\n".join(out) + "\n"


def render_costs(c: dict) -> str:
    b, q = c["briefs"], c["sequences"]
    out = ["# Costs", "", f"Generated {c['generated_at']}. Model costs are measured from the token usage logged for each "
           "brief and sequence in the current run, priced at the per-token rates set in the vertical's config. "
           "They cover one clean pass; samples, retries and regenerated drafts during development cost extra.", "",
           "| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |", "|---|---|---|---|---|---|---|",
           f"| Briefs | {b['model']} | {b['cost_items']} | {b['avg_input_tokens']} | {b['avg_output_tokens']} | ${b['avg_cost_usd']:.4f} | ${b['total_cost_usd']:.2f} |",
           f"| Sequences | {q['model']} | {q['cost_items']} | {q['avg_input_tokens']} | {q['avg_output_tokens']} | ${q['avg_cost_usd']:.4f} | ${q['total_cost_usd']:.2f} |",
           f"| **Model total** | | | | | | **${b['total_cost_usd'] + q['total_cost_usd']:.2f}** |", "",
           f"The items logged include {b['cost_items'] - b['written']} briefs and {q['cost_items'] - q['written']} sequences "
           "that are not current (groups that have since left tiers A and B, or text held back as out of date); they were "
           "paid for. A draft that was rewritten replaces its earlier row, so the cost of the earlier version is not in these totals.", ""]
    if c["other_costs"]:
        out += ["## Other costs (estimates written by hand)", "", "These are not logged by the pipeline. They are estimates from request counts and list prices, typed into the vertical's evals.yaml.", "",
                "| Item | Requests | Estimated cost | Basis |", "|---|---|---|---|"]
        out += [f"| {o['item']} | {o['requests']} | {o['estimate']} | {o['basis']} |" for o in c["other_costs"]]
        out += [""]
    out += ["Scoring, export, anonymization and this report make no paid calls."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vertical", default=DEFAULT_VERTICAL)
    args = parser.parse_args()
    main(args.vertical)
