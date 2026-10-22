# Territory Engine

A territory engine for a sales team. Give it a metro and a vertical, and it finds the accounts there from public sources, ranks them by public signs that they need help now, and drafts a short brief and a first outreach sequence for the top accounts. Every statement in a brief or email cites a numbered fact with its source, and code (not the model) checks that.

The shipped demo targets **home care, home health and hospice agencies in New York City**, for a seller of workforce-operations software. A new vertical or metro is a new config folder or file, not new code. That was tested once: a second vertical (residential HVAC, plumbing and electrical contractors in Phoenix) ran on config alone after two fixes to the core that it exposed; `docs/second-vertical.md` lists every core file that changed.

## What a sales leader gets

| Output | What it is | Where |
|---|---|---|
| Ranked account list | Every account found, with a tier (A to D), a score out of 100, the points per criterion and a plain-language reason for each, and a data-coverage figure so "we could not find out" is not confused with "poor fit". Locations of one operator are grouped. | `outputs/raw/accounts_scored.csv` (private) |
| Account briefs | One page per tier A and B group: who it is, why now, one way to open, what we do not know, and the numbered facts with source links and collection dates. | `outputs/raw/briefs/` (private) |
| Outreach drafts | A first email, a follow-up and a call opener per group, written for the likely buyer role and built on the same facts. Drafts for a rep to review, not auto-send. | `outputs/raw/sequences/` (private) |
| CRM and sequencing imports | CSVs mapped for Salesforce accounts and Outreach account fields, and a direct push of companies to HubSpot (`make hubspot-setup`, `make push-hubspot`). | `outputs/raw/exports/`, guide in `docs/stack-fit.md` |
| Report card and demo site | What was measured, what was not, and what it cost, plus an anonymized, browsable copy of the list, briefs and drafts. | `outputs/public/report_card.md`, `site/index.html` |

**The NYC run (signals collected 2026-10-12 to 2026-10-13):** 1,501 accounts in 1,415 groups, of which 33 groups are tier A and 211 tier B. Discover dropped 48 accounts outside the city's zips and kept 1,514; 13 more were left out by review because they are not home care providers (a pharmacy, nursing homes, consultancies, two pest-control companies), found by checking flagged names against the state's licensed home care list. That list is now matched to every account: 532 of the 1,501 matched and 969 did not (215 of the 244 groups in tiers A and B matched, 29 did not). Model cost was about $0.03 per brief and $0.02 per sequence. The report card has the full, current numbers; they are computed from the output files, not typed in.

**What it saves:** not measured yet. No timed comparison of a rep's manual research against the engine has been done, so this README makes no time-saved claim. `V2.md` lists the study that would measure it.

## How it works

1. **Discover**: pull every matching organization from the national provider registry and Google Maps, merge duplicates, drop zips outside the territory.
2. **Backfill**: find a website for registry-only accounts, accepting a match only on phone, or on zip plus a near-identical name. Every lookup is cached.
3. **Enrich**: read each account's own website for a careers page, hiring system and open roles; check the site is live; read the registry enrollment date; match the account to the state's licensed-provider list. "Could not check" is recorded separately from "none found".
4. **Score**: apply the rubric in `rubric.yaml`. Every point has a rule and a reason.
5. **Brief and sequence**: code builds the facts; the model only arranges and phrases them. A code check fails any statement without a cited fact, with a number not in its cited facts, or with a capitalised word (a place, an organization, a job title) not in its cited facts.
6. **Export and publish**: write the import files; build the anonymized public copy and run a leak test across every published file.
7. **Refresh and triggers**: `make refresh` keeps a copy of the last run, re-checks every signal, re-scores and rewrites only the drafts whose facts changed. `make triggers` lists accounts whose tier, hiring evidence, open-role range, website or licence status moved since the last saved run. `docs/monday-playbook.md` is a draft of how a rep would use the list.

## Limits, stated plainly

- **The list is not complete.** Against New York State's register of licensed providers in the same zip codes, this list contains 503 of 664, or 75.8%. Allowing for near-misses on the name it is about 78%, and 139 licensed providers in the territory are absent entirely. Run `make recall` to reproduce it. The register covers only businesses holding that licence, so recall against the whole market is still unknown.
- **The briefs are accurate but thin.** A model that had not seen the pipeline graded 15 briefs blind, twice. It rated their accuracy 4.5 out of 5 and their usefulness 2.1 out of 5, and would contact 1 of the 15 this week. Only 1.5% of accounts have a readable count of open roles, so for most of the list the strongest available fact is that a careers page exists. `outputs/public/project_review.md` has the detail.
- **The rubric is my judgment.** Its weights and tier cut-offs are a starting hypothesis. They have not been tested against meetings booked or deals won, because no outcome data exists yet.
- **Hiring signals are thin.** Most accounts have no website on file, and few careers pages publish a readable job feed, so most of the list is scored with low data coverage.
- **No contacts.** The engine finds accounts, not people. A sequence needs a named contact from another tool.
- **Nothing has been sent, and only one CRM load is proven.** Reply rates are unknown. On 2026-10-21 the 396 tier A to C accounts of the anonymized build were pushed to a HubSpot developer test account as companies, and an identical second push created 0 and changed 0. That proves the HubSpot company push only: the Salesforce and Outreach files have still not been imported into a live workspace, and no contacts were loaded anywhere.
- **One weekly refresh, not a history.** `make refresh` ran once, on 2026-10-22, about a week after the 2026-10-12 to 2026-10-13 collection: 15 of 1,501 accounts changed tier, the trigger list fired 55 events on 32 accounts, and 12 briefs and 12 sequences were rewritten. One pair is not a rate, part of the change may be noise (a website that did not answer one week), and no rep has said whether the triggers are worth acting on. The Monday playbook is a draft that no sales team has used.
- **The licence check matches by name and phone only.** `not_found` means no match, not that the account is unlicensed: it may trade under another name. A spot check found 8 of 8 matches correct and 6 of 6 `not_found` accounts absent from the state list; that is 14 accounts, not a measured error rate. Accounts that are not home care providers may remain, mostly in the lower tiers.
- **Anonymization is not a guarantee.** Names, addresses, phones, websites, IDs and hiring systems are removed and counts are shown as ranges, but a combination of facts (city, number of locations, years registered) may still point to an account.

The report card's "Not measured" section has the full list, and `outputs/public/project_review.md` is a full review of what this project does and does not prove.

## Run it

```
python3 -m pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env        # add the Google Maps and Anthropic keys
make discover backfill enrich score   # paid Google calls in discover and backfill
make brief sequence                   # paid model calls
make export public
make checks                           # check-generic, tests, leak test
make triggers                         # what changed since the last saved run
make refresh                          # weekly: re-check signals, rewrite out-of-date drafts
make fresh                            # monthly: save this run, re-discover, re-check everything
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
| `docs/` | Runbook, stack-fit guide and the Monday playbook (draft) |
| `V2.md` | What is not built, and what each item needs |
