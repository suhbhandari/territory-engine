# Operator runbook

How to set up, run, extend, and recover the territory engine. This describes the code as of 2026-10-08. Run all commands from the project root.

Eight steps work today:

1. **Discover** builds the account list for one metro and one vertical from two public sources: the national provider registry (NPPES) and Google Maps.
2. **Backfill** looks up each registry-only account on Google Maps to fill in its website.
3. **Enrich** looks up public signals for each account: job postings, website status, and registration age.
4. **Score** ranks and tiers the accounts using the vertical's rubric.
5. **Brief** writes a one-page, source-linked brief for each top-tier account group.
6. **Sequence** drafts a three-touch outreach sequence for each of those groups, built on the same facts.
7. **Export** writes import-ready CSV files for the CRM and the sales engagement tool.
8. **Public** builds the anonymized dataset, report card and cost summary that the demo site reads.

The weekly refresh is not built yet (section 7).

## 1. Setup

**Python.** Use Python 3.9 or newer. Nothing in the project pins a version; the code uses syntax that needs 3.9 and has been run on 3.9.6.

**Install the libraries.**

```
python3 -m pip install -r requirements.txt
```

Four packages: `requests` (web calls), `pandas` (tables and CSVs), `python-dotenv` (reads the key file), `PyYAML` (reads the config files).

**Create the key file.** The Google Maps source needs an API key. It lives in `.env`, which is excluded from version control so the key is never shared by accident.

```
cp .env.example .env
```

Open `.env` and replace each `your_key_here`. `GOOGLE_MAPS_API_KEY` is needed for discover and backfill. `ANTHROPIC_API_KEY` is needed for briefs and sequences. If the API answers that the key is not scoped to a workspace, also set `ANTHROPIC_WORKSPACE_ID`.

**Enable the right Google API.** In Google Cloud Console, the project that owns the key must have **Places API (New)** enabled, with billing on. This is easy to get wrong: Google lists an older API called simply "Places API" beside it. The engine does not use the older one (calling it without enabling it returns `REQUEST_DENIED`), and a key with only the older one enabled is rejected by the new one. If the key is restricted to specific APIs, add Places API (New) to its allowed list.

The provider registry needs no key and no account.

## 2. Running it

Run in this order. Backfill and enrich read the file that discover writes.

| Order | Command | What it does | Reads | Writes |
|---|---|---|---|---|
| 1 | `make discover` | Queries each source in the vertical's `discovery.yaml`, keeps results inside the metro's state and zip prefixes, and merges duplicates (same name and zip, or same phone) into one account. | `config/metro/nyc.yaml`, `config/verticals/home_care_post_acute/discovery.yaml`, `.env` | `outputs/raw/accounts_raw.csv`, overwritten every run |
| 2 | `make backfill` | For each account with no website that Google Maps did not already find, searches Google Maps for its name and address. Accepts a listing only if the phone matches, or the zip matches and the name is near-identical; otherwise the website stays blank. | `outputs/raw/accounts_raw.csv`, the `backfill:` block in `discovery.yaml`, `.env`, `outputs/raw/backfill_cache.csv` | `outputs/raw/accounts_raw.csv` (websites filled in), `outputs/raw/backfill_cache.csv` |
| 3 | `make enrich-sample` | Enriches the first 10 accounts only. A cheap check that the signals work before a full run. | `outputs/raw/accounts_raw.csv`, `config/verticals/home_care_post_acute/signals.yaml` | `outputs/raw/signals_raw.csv` |
| 4 | `make enrich` | Runs every signal in `signals.yaml` for every account that still needs it. Saves after every 20 accounts. | same as above, plus the existing `signals_raw.csv` | `outputs/raw/signals_raw.csv`, updated in place |
| 5 | `make score` | Joins accounts with signals, applies the rubric, and writes a ranked list with a tier, a score out of 100, the points per criterion, and a plain-language reason for each. Calls no external service, so re-run it freely after editing the rubric. | `accounts_raw.csv`, `signals_raw.csv`, `config/verticals/home_care_post_acute/rubric.yaml` | `outputs/raw/accounts_scored.csv` |
| 6 | `make brief-sample` then `make brief` | Writes one brief per account group in the tiers named in `brief.yaml` (`brief-sample` writes the first 5). Code builds a numbered fact list with a source link for each fact; the model may only arrange and phrase those facts and must cite a fact id for every statement. A code check then fails any brief with an uncited statement or a number that is not in its cited facts. Skips briefs already written. `python3 src/brief.py --dry-run` prints the facts and calls nothing. | `accounts_scored.csv`, `brief.yaml` and `brief_prompt.md` in the vertical folder, `.env` | `outputs/raw/briefs/*.md`, `outputs/raw/briefs/briefs_index.csv` (check result, tokens and cost per brief) |
| 7 | `make sequence-sample` then `make sequence` | Drafts the touches defined in `sequence.yaml` (today: email, follow-up email, call opener) for each group in its tiers, written for the role chosen by `personas.yaml`. Uses the same numbered facts as the brief. Code checks each touch for a cited fact, unsupported numbers, word and subject limits, and stray merge fields; failures are flagged "do not send without review". `--redo-failed` regenerates flagged ones; `--dry-run` calls nothing. | `accounts_scored.csv`; `sequence.yaml`, `personas.yaml`, `sequence_prompt.md`, `seller_context.md`, `brief.yaml` in the vertical folder; `.env` | `outputs/raw/sequences/*.md`, `sequences.csv` (one row per touch), `sequences_index.csv` (check result, tokens, cost) |
| 8 | `make export` | Writes one CSV per target in `export.yaml`: accounts for the CRM, and one row per account group carrying its outreach copy for the sales engagement tool. Sequences that failed their checks are left out. Calls no external service. See `docs/stack-fit.md` for field mapping and import steps. | `accounts_scored.csv`, `sequences/sequences.csv`, `briefs/briefs_index.csv`, `export.yaml` and `sequence.yaml` in the vertical folder | `outputs/raw/exports/*.csv` |
| 9 | `make public` | Builds `outputs/public/`: an anonymized copy of the scored accounts, briefs and sequences (aliases instead of names; addresses, phones, websites and IDs replaced), then the report card and cost summary computed from the run's own files. If any account's name words, domain, phone or ID survive in its published text, the build fails and writes nothing. | everything in `outputs/raw/`; `rubric.yaml`, `glossary.yaml`, `sequence.yaml`, `evals.yaml` | `outputs/public/site_data.json` and `.js`, `accounts_public.csv`, `report_card.json`, `.js` and `.md`, `costs.md` |
| 10 | `make site` | Rebuilds the public data and serves the repo at `http://localhost:8000/site/`. The site is one static page, `site/index.html`, with no build step; it can also be opened directly as a file. | `outputs/public/*.js` | nothing |
| any time | `make check-generic` | Scans core code and docs for vertical-specific terms and prints PASS or FAIL. Calls no external service. | text and code files outside `config/verticals/` and `outputs/` | nothing |

Worth knowing:

- **The make targets always use the defaults**: metro `config/metro/nyc.yaml`, vertical `home_care_post_acute`. For anything else, call the scripts directly (section 3).
- **Account file columns**: `name`, `address`, `city`, `state`, `zip`, `phone`, `website`, `source`, `license_type`, `entity_id`. `source` shows which source found the account; one found by both lists both. `entity_id` is the registry number when the registry found the account, otherwise the Google place ID.
- **Reference run.** The current NYC run produced 1,546 accounts: 1,238 registry only, 167 Google Maps only, 141 in both. Discover prints this breakdown at the end; use it to spot a source that silently returned nothing.
- **Backfill cache.** `backfill_cache.csv` records every lookup, hit or miss, with the listing it matched. Lookups already in it are never repeated, so re-running backfill is free. Discover overwrites the account file and wipes the filled-in websites; run `make backfill` again afterwards to restore them from the cache. Do not delete the cache unless you mean to pay for the lookups again.
- **Signals file.** One row per account. Each signal adds its data columns plus its own error column (`careers_page_error`, `http_check_error`, `npi_age_error`). An empty error cell means that signal finished for that account. Anything else is tried again on the next run, and only the signals that need it are re-run.
- **Job postings come from each account's own website.** The `careers_page` signal finds the careers page, identifies the applicant-tracking system behind it, and counts postings where that system publishes a readable feed (Greenhouse, Lever, Workday today). It never fetches external job boards, and it honours each site's robots.txt. Always read `jobs_status` before `jobs_total`: `no_website` means not checked, `counted` means a full feed was read, `listings_found` means `jobs_total` is a floor, and the other values mean a careers page or system was seen but no count was possible. The full list is at the top of `src/signals/careers_page.py`.
- **Locations of one operator are grouped.** Accounts that share a website domain get the same `group_rank` and sit together in the scored file, best location first (`rank_in_group`), so one operator takes one place in the ranking. Work the list by `group_rank`. Franchise locations share the franchisor's domain, so they group together even when the owners differ.
- **Read `data_coverage` next to the score.** It is the share of the rubric judged on real data. A low score with low coverage means "we could not find out", not "poor fit". Weights and tier cut-offs live in `rubric.yaml` and are a starting hypothesis; no outcome data has been used to fit them.
- **Enrich is slow on purpose.** Signals marked `sequential` in `signals.yaml` pause 1.2 seconds between accounts to stay polite to the service they call. For the NYC list that is about half an hour of waiting per sequential signal.
- **`outputs/raw/` holds real business names** and is meant to stay uncommitted. `outputs/public/` is the only output folder meant for git and for the public site.
- **Anonymization removes names and contact details, not every clue.** An account's combination of facts (an exact open-role count, a hiring system, a borough) may still point to it. Read a sample of `outputs/public/site_data.json` before publishing a new run.

## 3. Adding a new metro

A metro file holds geography only. Copy `config/metro/nyc.yaml` to `config/metro/<name>.yaml` and edit:

| Key | Meaning |
|---|---|
| `metro` | Short label printed in the run log. Required. |
| `state` | Two-letter state code. Both sources drop anything outside it. One state per file. |
| `city` | Main city name. Used for Google searches only when `search_cities` is empty. |
| `search_cities` | Place names to search Google Maps for. Each is combined with every search phrase in the vertical's `discovery.yaml`, so more names means more coverage and more billed requests. Use the names locals use (NYC lists its five boroughs). |
| `zip_prefixes` | The first three digits of the zip codes that make up the territory. The registry is queried once per prefix, and Google results outside these prefixes are dropped. |

**Choosing zip prefixes.** Look up which 3-digit prefixes cover the area you mean and list all of them. Put each in quotes (`"021"`, not `021`). Unquoted, they are read as numbers: leading zeros are lost and the run crashes.

**Check for spill.** A 3-digit prefix follows postal boundaries, not city or county lines. NYC's `110` prefix also covers part of neighbouring Nassau County and pulled 42 out-of-area accounts into the NYC list. After a first run, sort the output by `city` and `zip` and look for places that do not belong. There is no exclusion setting today: remove the rows by hand, or drop the prefix and accept the gap.

**Run it.**

```
python3 src/discover.py --metro config/metro/<name>.yaml
python3 src/backfill.py --limit 30
python3 src/backfill.py
python3 src/enrich.py --limit 10
python3 src/enrich.py
```

Discover always writes to `outputs/raw/accounts_raw.csv`, so copy the previous metro's account file elsewhere first. Enrich adds to whatever signals file it finds, so give each metro its own with `--accounts <path>` and `--output <path>`, or move the old `signals_raw.csv` aside. `enrich.py` also accepts `--metro` but does not use it; it enriches whatever account file it is given.

## 4. Adding a new vertical

The rule: **nothing specific to an industry may live in core code.** Search phrases, registry categories, job-title keywords, and display labels live in `config/verticals/<name>/`. That is what lets the engine be pointed at a different industry by adding a folder, not by rewriting code.

Files in the shipped vertical's folder today:

| File | Purpose |
|---|---|
| `discovery.yaml` | Which sources to run and their parameters: registry category names to search and keep, and Google search phrases with `{city}` and `{state}` placeholders. Also the `backfill:` block: which fields to fill and the search text used to find an account's listing. |
| `signals.yaml` | Which signals to run, the code module for each, how it runs (`mode: parallel` or `sequential`, and `delay` in seconds), and the keywords that sort job titles into role groups. |
| `glossary.yaml` | Display labels (account types, buyer titles, pain points) for briefs and the web app. Nothing reads it yet. |
| `rubric.yaml` | Scoring criteria, their weights, the rules that award points, and the tier cut-offs. |
| `seller_context.md` | One paragraph describing what the seller offers. Inserted into both prompts, so edit it in one place. |
| `brief.yaml`, `brief_prompt.md` | Which tiers get briefs, the fact templates and their source links, the "what we don't know" lines, and the instructions the model follows. |
| `evals.yaml` | The plain-language statements the report card prints: what the checks cover, what has not been measured, and cost estimates the pipeline does not log itself. Keep these current by hand. |
| `export.yaml` | The export files: which rows and tiers each holds, its columns, and how merge fields are translated for the sending tool. |
| `sequence.yaml`, `sequence_prompt.md`, `personas.yaml` | The touches in a sequence and their limits, the writing instructions, and the rules that pick which role a sequence is written for. |


To add a vertical, create the folder, write those files, and pass `--vertical <name>` to both scripts. Each key under `sources:` in `discovery.yaml` must match a module in `src/sources/` (today `nppes` and `google_maps`). A source that does not exist yet is new code for a developer, and it must follow the shared `fetch(params, geo)` interface and stay generic.

`make check-generic` enforces the rule. It fails if a term on its list appears in core code or in a doc like this one. A PASS is required before a phase can be called complete. Its term list is written for the shipped vertical, so a new vertical needs its own terms added to `scripts/check_generic.py`.

## 5. Failure modes and fixes

| Symptom | Cause | Fix |
|---|---|---|
| Google Maps source reports 0 records and prints `GOOGLE_MAPS_API_KEY not set — skipping` | `.env` is missing or the variable is blank. | Create `.env` from `.env.example` and add the key. |
| Google Maps source reports 0 records and prints a `failed:` line for every search | Google rejected the key. Most often Places API (New) is not enabled on the key's project and only the legacy API is. Billing off or a key restriction look the same. | Read the message after `failed:`. Enable Places API (New), confirm billing, check the key's API restrictions. |
| Registry source prints `hit 1200-record cap, results truncated` | One category-and-prefix query matched more records than the registry API will page through. Accounts past the cap are missing. | Use narrower zip prefixes so each query stays under the cap. |
| Registry source prints `error at skip=N` | A network or registry error mid-query. The rest of that query is dropped and the run continues with a partial list. | Re-run discover and compare the total with a previous run. |
| Discover prints `[skip] src.sources.<x> not found` | A source name in `discovery.yaml` has no matching module in `src/sources/`. | Fix the name, or have the module built. |
| Discover crashes with `KeyError: 'metro'` or a `startswith` type error | The metro file lacks the `metro` key, or zip prefixes are not quoted. | Add the key; quote every prefix. |
| Backfill reports many `error` lookups mentioning `Quota exceeded ... per minute` | Google's per-minute request limit was hit. Failed lookups are not saved as done. | Re-run `make backfill`; it retries only the failures. If it keeps happening, lower `_MAX_PER_MINUTE` in `src/backfill.py`. |
| Enrich crashes because `accounts_raw.csv` does not exist | Discover has not been run. | Run discover first. |
| Job-posting columns are empty for most accounts | Expected. Only accounts with a website can be checked, and only some careers pages expose a readable feed. | Read `jobs_status` for the reason per account. An empty `jobs_total` means "unknown", never "zero". |
| `jobs_status` is `site_unreachable` for a site that opens in a browser | The site refuses requests that identify themselves as a crawler. The engine does not disguise itself. | None. Treat the account as unchecked. |
| Enrich prints `[<signal>] 5 consecutive errors` then `disabled for the rest of this run` | A signal failed five times in a row, so enrich switched it off to avoid wasting the run. Affected accounts get `skipped: signal disabled...` in that signal's error column. | Read the error printed with the message, fix the cause, and re-run `make enrich`; only the skipped signal is retried. |
| `website_live` is `False` with no SSL value for most accounts | Only accounts with a Google Maps listing carry a website: 526 of 1,546 (34%) in the current NYC run after backfill. Backfill found no confident listing for 928 of the 1,238 registry-only accounts, so there is nothing to check for them. | Run `make backfill` if it has not been run since the last discover. Otherwise expected. `False` here means "no website on file or not reachable", not "site is down". |
| Registration-age columns are empty for some accounts | The lookup needs a registry number, and Google-Maps-only accounts do not have one. | Expected. A real lookup failure shows in `npi_age_error` and is retried next run. |
| Enrich was interrupted partway | Closed laptop, lost network, Ctrl-C. | Re-run `make enrich`. Progress is saved after every 20 accounts (`--batch-size` changes this), so at most one batch is lost and the run picks up where it stopped. |
| Some accounts show a value in a `<signal>_error` column after a full run | That signal failed for those accounts (timeout, service error). | Re-run `make enrich`; only failed signals are retried. To redo everything, move or delete `signals_raw.csv` first. |
| Brief or sequence run reports `error` with `credit balance is too low` | The Anthropic account behind the key has no credit. Nothing is charged for these. | Add credit to the same organization the key belongs to, then re-run; only missing items are written. |
| A brief or sequence file opens with a "check failed" banner | The draft cited no fact, used a number that is not in its cited facts, or broke a length rule. | Re-run with `--redo-failed`. The check only covers digits, citations and length; it does not catch a wrong word, so drafts still need a human read before sending. |
| `make check-generic` prints FAIL | A vertical-specific term is in core code or a doc. The output lists file and line. | Move the term into `config/verticals/<name>/`, or reword. |

## 6. Costs

| Item | Cost |
|---|---|
| Provider registry (discovery and the registration-age signal) | Free. No key. |
| Job-postings and website signals | Free. No key. They read the accounts' own websites. |
| Google Maps discovery | Paid, per request. |
| Google Maps backfill | Paid, one request per account missing a website. Free on re-runs (cached). |
| Briefs | Paid, on the Anthropic API. Measured on the NYC run: about $0.02 per brief, $5.50 for 276. Logged per brief in `briefs_index.csv`. |
| Sequences | Paid, on the Anthropic API. Measured on the NYC run: about $0.02 per sequence, $5.15 for 276. Logged in `sequences_index.csv`. |

The Google call is Places Text Search. Because the engine asks for website and phone in the same call, Google bills it at its higher "Enterprise" tier, list price roughly $35 per 1,000 requests. One NYC discovery run is 15 searches (5 place names × 3 search phrases), each up to 3 pages, so at most 45 requests: about $1.50 at list price, before any free monthly allowance.

For a new metro, estimate: number of `search_cities` × number of search phrases × 3 pages. Every re-run of discover is billed again. Enrich makes no Google calls.

Backfill is the larger cost: one request per registry-only account at the same tier. The NYC run made 1,238 lookups, about $43 at list price before any free monthly allowance. That is paid once per metro; the cache makes later runs free until new accounts appear.

**Confirm current prices on Google's Maps Platform pricing page before relying on these numbers.** Tiers and free allowances change.

## 7. What is not built yet

No commands exist for any of these:

- Weekly refresh

**Dropped from v1: the objection library.** It was planned as a set of objections drawn from real conversations with operators. No such conversations have been recorded, and a library written without them would be invented, so it is left out.
