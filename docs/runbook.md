# Operator runbook

How to set up, run, extend, and recover the territory engine. This describes the code as of 2026-10-08. Run all commands from the project root.

Three steps work today:

1. **Discover** builds the account list for one metro and one vertical from two public sources: the national provider registry (NPPES) and Google Maps.
2. **Backfill** looks up each registry-only account on Google Maps to fill in its website.
3. **Enrich** looks up public signals for each account: job postings, website status, and registration age.

Scoring, briefs, outreach, and CRM export are not built yet (section 7).

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

Open `.env` and replace `your_key_here` with your key. The only variable is `GOOGLE_MAPS_API_KEY`.

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
| any time | `make check-generic` | Scans core code and docs for vertical-specific terms and prints PASS or FAIL. Calls no external service. | text and code files outside `config/verticals/` and `outputs/` | nothing |

Worth knowing:

- **The make targets always use the defaults**: metro `config/metro/nyc.yaml`, vertical `home_care_post_acute`. For anything else, call the scripts directly (section 3).
- **Account file columns**: `name`, `address`, `city`, `state`, `zip`, `phone`, `website`, `source`, `license_type`, `entity_id`. `source` shows which source found the account; one found by both lists both. `entity_id` is the registry number when the registry found the account, otherwise the Google place ID.
- **Reference run.** The current NYC run produced 1,546 accounts: 1,238 registry only, 167 Google Maps only, 141 in both. Discover prints this breakdown at the end; use it to spot a source that silently returned nothing.
- **Backfill cache.** `backfill_cache.csv` records every lookup, hit or miss, with the listing it matched. Lookups already in it are never repeated, so re-running backfill is free. Discover overwrites the account file and wipes the filled-in websites; run `make backfill` again afterwards to restore them from the cache. Do not delete the cache unless you mean to pay for the lookups again.
- **Signals file.** One row per account. Each signal adds its data columns plus its own error column (`indeed_jobs_error`, `http_check_error`, `npi_age_error`). An empty error cell means that signal finished for that account. Anything else is tried again on the next run, and only the signals that need it are re-run.
- **Enrich is slow on purpose.** Signals marked `sequential` in `signals.yaml` pause 1.2 seconds between accounts to stay polite to the service they call. For the NYC list that is about half an hour of waiting per sequential signal.
- **`outputs/raw/` holds real business names** and is meant to stay uncommitted.

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

`CLAUDE.md` also plans `rubric.yaml`, `personas.yaml`, and a brief prompt per vertical. They do not exist yet because the phases that use them are not built.

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
| Enrich prints `[indeed_jobs] 5 consecutive errors` then `disabled for the rest of this run`; job columns are empty and `indeed_jobs_error` holds an HTTP error or `skipped: signal disabled...` on every account | The job board rejects the request. **This source is currently broken**, and a replacement is an open decision. Enrich switches a signal off after 5 failures in a row so it does not waste the run. | None for the operator. Treat all job-posting columns as empty. Because of this, enrich reports every account as still needing work on each run; the other signals are not repeated. |
| `website_live` is `False` with no SSL value for most accounts | Only accounts with a Google Maps listing carry a website: 526 of 1,546 (34%) in the current NYC run after backfill. Backfill found no confident listing for 928 of the 1,238 registry-only accounts, so there is nothing to check for them. | Run `make backfill` if it has not been run since the last discover. Otherwise expected. `False` here means "no website on file or not reachable", not "site is down". |
| Registration-age columns are empty for some accounts | The lookup needs a registry number, and Google-Maps-only accounts do not have one. | Expected. A real lookup failure shows in `npi_age_error` and is retried next run. |
| Enrich was interrupted partway | Closed laptop, lost network, Ctrl-C. | Re-run `make enrich`. Progress is saved after every 20 accounts (`--batch-size` changes this), so at most one batch is lost and the run picks up where it stopped. |
| Some accounts show a value in a `<signal>_error` column after a full run | That signal failed for those accounts (timeout, service error). | Re-run `make enrich`; only failed signals are retried. To redo everything, move or delete `signals_raw.csv` first. |
| `make check-generic` prints FAIL | A vertical-specific term is in core code or a doc. The output lists file and line. | Move the term into `config/verticals/<name>/`, or reword. |

## 6. Costs

| Item | Cost |
|---|---|
| Provider registry (discovery and the registration-age signal) | Free. No key. |
| Job-postings and website signals | Free. No key. |
| Google Maps discovery | Paid, per request. |
| Google Maps backfill | Paid, one request per account missing a website. Free on re-runs (cached). |
| LLM usage | None. The brief-writing phase is not built. |

The Google call is Places Text Search. Because the engine asks for website and phone in the same call, Google bills it at its higher "Enterprise" tier, list price roughly $35 per 1,000 requests. One NYC discovery run is 15 searches (5 place names × 3 search phrases), each up to 3 pages, so at most 45 requests: about $1.50 at list price, before any free monthly allowance.

For a new metro, estimate: number of `search_cities` × number of search phrases × 3 pages. Every re-run of discover is billed again. Enrich makes no Google calls.

Backfill is the larger cost: one request per registry-only account at the same tier. The NYC run made 1,238 lookups, about $43 at list price before any free monthly allowance. That is paid once per metro; the cache makes later runs free until new accounts appear.

**Confirm current prices on Google's Maps Platform pricing page before relying on these numbers.** Tiers and free allowances change.

## 7. What is not built yet

No commands exist for any of these:

- Scoring accounts against a rubric
- Account briefs
- Outreach sequences
- CRM export
- Web app
- Weekly refresh
