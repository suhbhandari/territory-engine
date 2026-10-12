# Territory Engine

A territory engine for a sales team. Give it a metro and a vertical, and it finds the accounts there from public sources, ranks them by public signs that they need help now, and drafts a short brief and a first outreach sequence for the top accounts. Every statement in a brief or email cites a numbered fact with its source, and code (not the model) checks that.

The shipped demo targets **home care, home health and hospice agencies in New York City**, for a seller of workforce-operations software. A new vertical or metro is a new config folder or file, not new code.

## What a sales leader gets

| Output | What it is | Where |
|---|---|---|
| Ranked account list | Every account found, with a tier (A to D), a score out of 100, the points per criterion and a plain-language reason for each, and a data-coverage figure so "we could not find out" is not confused with "poor fit". Locations of one operator are grouped. | `outputs/raw/accounts_scored.csv` (private) |
| Account briefs | One page per tier A and B group: who it is, why now, one way to open, what we do not know, and the numbered facts with source links and collection dates. | `outputs/raw/briefs/` (private) |
| Outreach drafts | A first email, a follow-up and a call opener per group, written for the likely buyer role and built on the same facts. Drafts for a rep to review, not auto-send. | `outputs/raw/sequences/` (private) |
| CRM and sequencing imports | CSVs mapped for Salesforce accounts and Outreach account fields. | `outputs/raw/exports/`, guide in `docs/stack-fit.md` |
| Report card and demo site | What was measured, what was not, and what it cost, plus an anonymized, browsable copy of the list, briefs and drafts. | `outputs/public/report_card.md`, `site/index.html` |

**The NYC run (signals collected 2026-10-09):** 1,497 accounts in 1,414 groups, of which 33 groups are tier A and 234 tier B. Model cost was about $0.02 per brief and $0.02 per sequence. The report card has the full, current numbers; they are computed from the output files, not typed in.

**What it saves:** not measured yet. No timed comparison of a rep's manual research against the engine has been done, so this README makes no time-saved claim. `V2.md` lists the study that would measure it.

## How it works

1. **Discover**: pull every matching organization from the national provider registry and Google Maps, merge duplicates, drop zips outside the territory.
2. **Backfill**: find a website for registry-only accounts, accepting a match only on phone, or on zip plus a near-identical name. Every lookup is cached.
3. **Enrich**: read each account's own website for a careers page, hiring system and open roles; check the site is live; read the registry enrollment date. "Could not check" is recorded separately from "none found".
4. **Score**: apply the rubric in `rubric.yaml`. Every point has a rule and a reason.
5. **Brief and sequence**: code builds the facts; the model only arranges and phrases them. A code check fails any statement without a cited fact, with a number not in its cited facts, or with a capitalised word (a place, an organization, a job title) not in its cited facts.
6. **Export and publish**: write the import files; build the anonymized public copy and run a leak test across every published file.

## Limits, stated plainly

- **The rubric is my judgment.** Its weights and tier cut-offs are a starting hypothesis. They have not been tested against meetings booked or deals won, because no outcome data exists yet.
- **Hiring signals are thin.** Most accounts have no website on file, and few careers pages publish a readable job feed, so most of the list is scored with low data coverage.
- **No contacts.** The engine finds accounts, not people. A sequence needs a named contact from another tool.
- **Nothing has been sent or imported.** Reply rates are unknown, and the export files have not been loaded into a live CRM.
- **One snapshot.** There is no weekly refresh yet; the signals are from one collection date.
- **Anonymization is not a guarantee.** Names, addresses, phones, websites and IDs are removed and counts are shown as ranges, but a combination of facts may still point to an account.

The report card's "Not measured" section has the full list.

## Run it

```
python3 -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # add the Google Maps and Anthropic keys
make discover backfill enrich score   # paid Google calls in discover and backfill
make brief sequence                   # paid model calls
make export public
make checks                           # check-generic, tests, leak test
make site                             # http://localhost:8000/site/
```

`docs/runbook.md` covers setup, every command, adding a metro or a vertical, excluding accounts, failure modes and costs.

## Repo layout

| Path | What it holds |
|---|---|
| `config/defaults.yaml` | Which metro and vertical runs by default |
| `config/metro/` | Geography only: state, search cities, zip prefixes, excluded zips |
| `config/verticals/<name>/` | Everything vertical-specific: sources, signals, rubric, fact templates, prompts, personas, export columns, report-card text |
| `src/` | The generic engine; `src/sources/` and `src/signals/` hold the pluggable data sources |
| `scripts/` | `check_generic.py` (no vertical terms in core code) and `leak_test.py` |
| `tests/` | Tests with made-up data |
| `outputs/raw/` | Real names and contact details. Never committed. |
| `outputs/public/` | The anonymized build the site reads. Committed. |
| `docs/` | Runbook and stack-fit guide |
| `V2.md` | What is not built, and what each item needs |
