# Operator runbook

How to set up, run, extend, and recover the territory engine. This describes the code as of 2026-10-13. Run all commands from the project root.

Eight steps work today:

1. **Discover** builds the account list for one metro and one vertical from two public sources: the national provider registry (NPPES) and Google Maps.
2. **Backfill** looks up each registry-only account on Google Maps to fill in its website.
3. **Enrich** looks up public signals for each account: job postings, website status, registration age, and a match against the state's list of licensed providers.
4. **Score** ranks and tiers the accounts using the vertical's rubric.
5. **Brief** writes a one-page, source-linked brief for each top-tier account group.
6. **Sequence** drafts a three-touch outreach sequence for each of those groups, built on the same facts.
7. **Export** writes import-ready CSV files for the CRM and the sales engagement tool.
8. **Public** builds the anonymized dataset, report card and cost summary that the demo site reads.

Two more commands sit on top: `make triggers` lists what changed since the last saved run, and `make refresh` is the weekly routine. Both are built. Neither has been run on a weekly schedule yet (section 7 and `V2.md`).

## 1. Setup

**Python.** Use Python 3.9 or newer. Nothing in the project pins a version; the code uses syntax that needs 3.9. It has been run on 3.9.6 and, for the tests and checks, on 3.10.

**Install the libraries.**

```
python3 -m pip install -r requirements.txt
```

Five packages: `requests` (web calls), `pandas` (tables and CSVs), `python-dotenv` (reads the key file), `PyYAML` (reads the config files), `anthropic` (model calls for briefs and sequences; nothing else needs it).

To run the tests, also install `requirements-dev.txt` (pytest).

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
| 1 | `make discover` | Queries each source in the vertical's `discovery.yaml`, keeps results inside the metro's state and zip prefixes, merges duplicates (same name and zip, or same phone) into one account, and drops accounts in the metro's `exclude_zips`. Stamps each account with `discovered_at`. | `config/metro/nyc.yaml`, `config/verticals/home_care_post_acute/discovery.yaml`, `.env` | `outputs/raw/accounts_raw.csv`, overwritten every run; `outputs/raw/discover_summary.json` (rows fetched per source, rows merged, rows dropped) |
| 2 | `make backfill` | For each account with no website that Google Maps did not already find, searches Google Maps for its name and address. Accepts a listing only if the phone matches, or the zip matches and the name is near-identical; otherwise the website stays blank. | `outputs/raw/accounts_raw.csv`, the `backfill:` block in `discovery.yaml`, `.env`, `outputs/raw/backfill_cache.csv` | `outputs/raw/accounts_raw.csv` (websites filled in), `outputs/raw/backfill_cache.csv` |
| 3 | `make enrich-sample` | Enriches the first 10 accounts only. A cheap check that the signals work before a full run. | `outputs/raw/accounts_raw.csv`, `config/verticals/home_care_post_acute/signals.yaml` | `outputs/raw/signals_raw.csv` |
| 4 | `make enrich` | Runs every signal in `signals.yaml` for every account that still needs it. Saves after every 20 accounts. | same as above, plus the existing `signals_raw.csv` | `outputs/raw/signals_raw.csv`, updated in place |
| 5 | `make score` | Joins accounts with signals, applies the rubric, and writes a ranked list with a tier, a score out of 100, the points per criterion, and a plain-language reason for each. First it leaves out accounts in the metro's `exclude_zips` and accounts marked `exclude` in `outputs/raw/exclusions.csv` (section 2, "Excluding accounts"). Calls no external service, so re-run it freely after editing the rubric. | `accounts_raw.csv`, `signals_raw.csv`, `config/verticals/home_care_post_acute/rubric.yaml`, the metro file, `outputs/raw/exclusions.csv` | `outputs/raw/accounts_scored.csv`, `outputs/raw/accounts_excluded.csv` (with the reason for each) |
| 6 | `make brief-sample` then `make brief` | Writes one brief per account group in the tiers named in `brief.yaml` (`brief-sample` writes the first 5). Code builds a numbered fact list with a source link for each fact; the model may only arrange and phrase those facts and must cite a fact id for every statement. A code check then fails any brief with an uncited statement, a number (digits or a number word) that is not in its cited facts, or a capitalised word inside a sentence (a place, organisation or job title) that is not in its cited facts or in `allowed_words`. Skips briefs already written, unless they are out of date (see "Out-of-date text" below). `python3 src/brief.py --dry-run` prints the facts and calls nothing. | `accounts_scored.csv`, `brief.yaml` and `brief_prompt.md` in the vertical folder, `.env` | `outputs/raw/briefs/*.md`, `outputs/raw/briefs/briefs_index.csv` (check result, tokens and cost per brief) |
| 7 | `make sequence-sample` then `make sequence` | Drafts the touches defined in `sequence.yaml` (today: email, follow-up email, call opener) for each group in its tiers, written for the role chosen by `personas.yaml`. Uses the same numbered facts as the brief. Code checks each touch for a cited fact, unsupported numbers, word and subject limits, and stray merge fields; failures are flagged "do not send without review". `--redo-failed` regenerates flagged ones; `--dry-run` calls nothing. | `accounts_scored.csv`; `sequence.yaml`, `personas.yaml`, `sequence_prompt.md`, `seller_context.md`, `brief.yaml` in the vertical folder; `.env` | `outputs/raw/sequences/*.md`, `sequences.csv` (one row per touch), `sequences_index.csv` (check result, tokens, cost) |
| 8 | `make export` | Writes one CSV per target in `export.yaml`: accounts for the CRM, and one row per account group carrying its outreach copy for the sales engagement tool. Sequences that failed their checks are left out. Calls no external service. See `docs/stack-fit.md` for field mapping and import steps. | `accounts_scored.csv`, `sequences/sequences.csv`, `briefs/briefs_index.csv`, `export.yaml` and `sequence.yaml` in the vertical folder | `outputs/raw/exports/*.csv` |
| 9 | `make public` | Builds `outputs/public/`: an anonymized copy of the scored accounts, briefs and sequences (aliases instead of names; addresses, phones, websites and IDs replaced), then the report card and cost summary computed from the run's own files. Open-role counts are published as ranges. Briefs and sequences that are out of date are left out. If any account's name words, domain, phone or ID survive in its published text, the build fails and writes nothing. | everything in `outputs/raw/`; `rubric.yaml`, `glossary.yaml`, `sequence.yaml`, `evals.yaml` | `outputs/public/site_data.json` and `.js`, `accounts_public.csv`, `report_card.json`, `.js` and `.md`, `costs.md` |
| 10 | `make site` | Rebuilds the public data and serves the repo at `http://localhost:8000/site/`. The site is one static page, `site/index.html`, with no build step; it can also be opened directly as a file. | `outputs/public/*.js` | nothing |
| any time | `make check-generic` | Scans core code and docs for vertical-specific terms and prints PASS or FAIL. Docs are checked against a list of prose terms; code (`.py`, `.html`, `.js`, the Makefile) is also checked for role words and underscore names such as a vertical's folder name. Calls no external service. | files outside `config/verticals/`, `outputs/`, `tests/fixtures/`, and `README.md` (which describes the shipped demo run) | nothing |
| any time | `make test` | Runs the tests in `tests/` (parsers, dedupe, backfill matching, scoring, the brief and sequence checks, exclusions, out-of-date detection, anonymization and the leak test). Made-up data only; calls nothing. | `tests/` | nothing |
| any time | `make leak-test` | Searches every file in `site/` and `outputs/public/` for every account's name, address, phone, website, domain, careers URL and ID from `outputs/raw/`. Prints PASS or FAIL; never prints the values it finds. | `outputs/raw/`, `site/`, `outputs/public/`, and `outputs/raw/leak_allowlist.csv` if it exists | nothing |
| any time | `make snapshot` | Copies the current run's private files (accounts, signals, scores, exclusions, exports, draft indexes) into `outputs/raw/runs/<date>/`, labelled by the date most signals were collected. Refuses to overwrite a different snapshot. Never deletes. | `outputs/raw/` | `outputs/raw/runs/<date>/` |
| fresh run | `make fresh` | Snapshots the current run and moves its signals file into the snapshot (only after confirming the copy), then runs discover, backfill, enrich, score and export, so every account is re-found and every signal re-checked. Paid Google calls in discover, and in backfill for accounts not in the cache. About an hour, mostly enrich. Then rewrite the drafts (`make brief sequence`, then `--redo-failed`) and run `make public checks`. | as each step | as each step |
| weekly | `make triggers` | Compares the latest saved run in `outputs/raw/runs/` with the current scored list on the columns in `triggers.yaml` (tier, hiring evidence, open-role range, hiring system, website responds, state licence). Lists changed accounts, new accounts and gone accounts, with the rubric criteria whose points moved and the date each side was collected. Changes that only mean a check could not run are not listed. Calls nothing external. | the latest folder in `outputs/raw/runs/`, `outputs/raw/accounts_scored.csv`, `triggers.yaml` | `outputs/raw/triggers.csv` (private) |
| weekly | `make refresh` | Saves a copy of the current run, re-checks every signal, re-scores, writes the trigger list, rewrites only the briefs and sequences that are out of date, then exports, rebuilds the public copy and runs the checks. Paid model calls for the rewritten drafts only. Does not re-discover; `make fresh` does. The weekly and monthly rhythm is the Makefile's suggestion and has not been run on a schedule. | as each step | as each step |
| any time | `make stability` | Re-scores the current list with each rubric criterion's weight at half and at one and a half times, re-ranks, and prints how much of the top of the list is the same accounts afterwards. Reports it two ways: against a top group of the same size (the number to quote, because it isolates the order from the cut-off) and against the rubric's written cut-off scores. Reads the scored file only; calls nothing. | `outputs/raw/accounts_scored.csv`, `rubric.yaml` | prints; `--csv PATH` to save |
| any time | `make checks` | Runs `check-generic`, `test` and `leak-test` together. Run it before calling any change done. | | nothing |

Worth knowing:

- **Defaults and overrides.** Every script and make target uses the metro and vertical in `config/defaults.yaml` (today `config/metro/nyc.yaml` and `home_care_post_acute`). For another one, pass it to make, for example `make score METRO=config/metro/<name>.yaml VERTICAL=<name>`, or call the scripts with `--metro` and `--vertical`.
- **Account file columns**: `name`, `address`, `city`, `state`, `zip`, `phone`, `website`, `source`, `license_type`, `entity_id`. `discovered_at` (filled by discover runs from 2026-10-12 on) is when the account was collected. `source` shows which source found the account; one found by both lists both. `entity_id` is the registry number when the registry found the account, otherwise the Google place ID.
- **Reference run.** The 2026-10-12 NYC discover run fetched 2,120 rows (registry 1,759, Google Maps 361), merged 558 duplicates, dropped 48 outside the territory and kept 1,514 accounts: 1,194 registry only, 182 Google Maps only, 138 in both. Score leaves out 13 more by review, so the scored list has 1,501. Discover prints the source breakdown at the end and saves it in `discover_summary.json`; use it to spot a source that silently returned nothing.
- **Backfill cache.** `backfill_cache.csv` records every lookup, hit or miss, with the listing it matched. Lookups already in it are never repeated, so re-running backfill is free. Discover overwrites the account file and wipes the filled-in websites; run `make backfill` again afterwards to restore them from the cache. Do not delete the cache unless you mean to pay for the lookups again.
- **Signals file.** One row per account. Each signal adds its data columns plus its own error column (`careers_page_error`, `http_check_error`, `npi_age_error`). An empty error cell means that signal finished for that account. Anything else is tried again on the next run, and only the signals that need it are re-run.
- **Licence check.** The `state_license` signal (module `src/signals/open_data_match.py`) downloads the state's list of licensed providers once per run and matches each account by phone, exact name, or near-identical name in the same zip. `license_status` is `matched` or `not_found`; `not_found` is not proof the account is unlicensed, since it may trade under another name. The rubric's agency-type criterion uses it. The names on matched records (`license_names`) stay private.
- **Job postings come from each account's own website.** The `careers_page` signal finds the careers page, identifies the applicant-tracking system behind it, and counts postings where that system publishes a readable feed (Greenhouse, Lever, Workday today). It never fetches external job boards, and it honours each site's robots.txt. Always read `jobs_status` before `jobs_total`: `no_website` means not checked, `counted` means a full feed was read, `listings_found` means `jobs_total` is a floor, and the other values mean a careers page or system was seen but no count was possible. The full list is at the top of `src/signals/careers_page.py`.
- **Locations of one operator are grouped.** Accounts that share a website domain get the same `group_rank` and sit together in the scored file, best location first (`rank_in_group`), so one operator takes one place in the ranking. Work the list by `group_rank`. Franchise locations share the franchisor's domain, so they group together even when the owners differ.
- **Read `data_coverage` next to the score.** It is the share of the rubric judged on real data. A low score with low coverage means "we could not find out", not "poor fit". Weights and tier cut-offs live in `rubric.yaml` and are a starting hypothesis; no outcome data has been used to fit them.
- **Enrich is slow on purpose.** Signals marked `sequential` in `signals.yaml` pause 1.2 seconds between accounts to stay polite to the service they call. For the NYC list that is about half an hour of waiting per sequential signal.
- **`outputs/raw/` holds real business names** and is meant to stay uncommitted. `outputs/public/` is the only output folder meant for git and for the public site.
- **Anonymization removes names and contact details, not every clue.** Open-role counts are published as ranges and each account's hiring system is hidden, but an account's combination of facts (a borough, its number of locations, years registered) may still point to it. Read a sample of `outputs/public/site_data.json` before publishing a new run.
- **Websites that are not the account's own.** Backfill removes any website on a domain listed under `not_own_website_domains` in the vertical's `discovery.yaml` (state directories, licensing pages, listing sites), and any listed by entity ID in `outputs/raw/website_rejections.csv` (columns `entity_id`, `reason`; for a wrong match). Then run `make enrich`: the signals that read the website (`uses_website: true` in `signals.yaml`) re-run for those accounts only.
- **Excluding accounts.** Two ways, both applied by `make score`. (1) Zips: list 5-digit zips under `exclude_zips` in the metro file. (2) By review: `outputs/raw/exclusions.csv` has columns `entity_id`, `name`, `decision`, `reason` (plus context columns). Put `exclude` in `decision` and a short reason; any other value keeps the account. The 2026-10-12 review checked 29 flagged names against the state's list of licensed providers (NYS DOH Health Facility General Information on health.data.ny.gov) and its `evidence` column says so. The file holds real names, so it stays in `outputs/raw/` and is never committed. Then re-run `make score`, `make export` and `make public`. Each left-out account is listed with its reason in `outputs/raw/accounts_excluded.csv`, and the report card counts them.
- **Out-of-date text.** A saved brief or sequence is used only while its group still leads in a tier that gets text, its saved facts and their sources match what the code builds from the scored data now, and its text passes the checks as they are now. Otherwise it is out of date: export and `make public` leave it out, the report card counts it, and the next `make brief` or `make sequence` rewrites it (a paid call per item). Re-scoring after an exclusion, or tightening a check, can make text out of date.

## 3. Adding a new metro

A metro file holds geography only. Copy `config/metro/nyc.yaml` to `config/metro/<name>.yaml` and edit:

| Key | Meaning |
|---|---|
| `metro` | Short label printed in the run log. Required. |
| `state` | Two-letter state code. Both sources drop anything outside it. One state per file. |
| `city` | Main city name. Used for Google searches only when `search_cities` is empty. |
| `search_cities` | Place names to search Google Maps for. Each is combined with every search phrase in the vertical's `discovery.yaml`, so more names means more coverage and more billed requests. Use the names locals use (NYC lists its five boroughs). |
| `exclude_zips` | Optional. 5-digit zips inside those prefixes that are outside the territory. Quote each one. |
| `zip_prefixes` | The first three digits of the zip codes that make up the territory. The registry is queried once per prefix, and Google results outside these prefixes are dropped. |

**Choosing zip prefixes.** Look up which 3-digit prefixes cover the area you mean and list all of them. Put each in quotes (`"021"`, not `021`). Unquoted, they are read as numbers: leading zeros are lost and the run crashes.

**Check for spill.** A 3-digit prefix follows postal boundaries, not city or county lines. NYC's `110` prefix also covers part of neighbouring Nassau County and pulled 48 out-of-area accounts into the NYC list. After a first run, sort the output by `city` and `zip` and look for places that do not belong, then list those 5-digit zips under `exclude_zips` in the metro file. Discover drops them on its next run, and score leaves them out of the current data without a re-run.

**Run it.**

```
python3 src/discover.py --metro config/metro/<name>.yaml
python3 src/backfill.py --limit 30
python3 src/backfill.py
python3 src/enrich.py --limit 10
python3 src/enrich.py
```

Discover always writes to `outputs/raw/accounts_raw.csv`, so copy the previous metro's account file elsewhere first. Enrich adds to whatever signals file it finds, so give each metro its own with `--accounts <path>` and `--output <path>`, or move the old `signals_raw.csv` aside. `enrich.py` also accepts `--metro` but does not use it; it enriches whatever account file it is given. Score, brief, sequence, export and public read and write fixed paths under `outputs/raw/` and `outputs/public/`, so only one metro's results can sit there at a time (`V2.md`).

## 4. Adding a new vertical

The rule: **nothing specific to an industry may live in core code.** Search phrases, registry categories, job-title keywords, and display labels live in `config/verticals/<name>/`. That is what lets the engine be pointed at a different industry by adding a folder, not by rewriting code.

Files in the shipped vertical's folder today:

| File | Purpose |
|---|---|
| `discovery.yaml` | Which sources to run and their parameters: registry category names to search and keep, and Google search phrases with `{city}` and `{state}` placeholders. Also the `backfill:` block: which fields to fill and the search text used to find an account's listing. |
| `signals.yaml` | Which signals to run, the code module for each, how it runs (`mode: parallel` or `sequential`, and `delay` in seconds), and the keywords that sort job titles into role groups. |
| `glossary.yaml` | Display labels. The public build reads `vertical_name` for the site title; the other keys (account types, buyer titles, pain points) are not read by any code yet. |
| `rubric.yaml` | Scoring criteria, their weights, the rules that award points, and the tier cut-offs. |
| `seller_context.md` | One paragraph describing what the seller offers. Inserted into both prompts, so edit it in one place. |
| `brief.yaml`, `brief_prompt.md` | Which tiers get briefs, the fact templates and their sources (label, link, and the column holding the date the data was collected), `allowed_words` for the wording check, the "what we don't know" lines, and the instructions the model follows. |
| `evals.yaml` | The plain-language statements the report card prints: what the checks cover, what has not been measured, and cost estimates the pipeline does not log itself. Keep these current by hand. |
| `export.yaml` | The export files: which rows and tiers each holds, its columns, and how merge fields are translated for the sending tool. |
| `sequence.yaml`, `sequence_prompt.md`, `personas.yaml` | The touches in a sequence and their limits, the writing instructions, and the rules that pick which role a sequence is written for. |


To add a vertical, create the folder, write those files, and pass `VERTICAL=<name>` to the make targets (or `--vertical <name>` to each script), or change `config/defaults.yaml`. Each key under `sources:` in `discovery.yaml` must match a module in `src/sources/` (today `nppes` and `google_maps`). A source that does not exist yet is new code for a developer, and it must follow the shared `fetch(params, geo)` interface and stay generic.

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
| Enrich prints `[npi_age] 5 consecutive errors` with `ConnectionError`, or far more `site_unreachable` than the last run | The computer lost its internet connection during the run (Wi-Fi drop, lid closed). Since 2026-10-12 the website signals check a reference site before saving "unreachable", and raise instead if it also fails, so those accounts are retried. Runs before that saved them as unreachable. | Keep the computer awake and connected (`caffeinate -i`, lid open) and re-run `make enrich`; failed signals are retried. To re-check accounts saved as unreachable by an earlier run: `python3 src/enrich.py --redo careers_page,http_check --where jobs_status=site_unreachable`. |
| `jobs_status` is `site_unreachable` for a site that opens in a browser | The site refuses requests that identify themselves as a crawler. The engine does not disguise itself. | None. Treat the account as unchecked. |
| Enrich prints `[<signal>] 5 consecutive errors` then `disabled for the rest of this run` | A signal failed five times in a row, so enrich switched it off to avoid wasting the run. Affected accounts get `skipped: signal disabled...` in that signal's error column. | Read the error printed with the message, fix the cause, and re-run `make enrich`; only the skipped signal is retried. |
| `website_live` is `False` with no SSL value for most accounts | Only accounts with a Google Maps listing carry a website: about a third of the NYC list after backfill (the report card has the current share). Backfill found no confident listing for 929 of the 1,252 registry-only accounts it looked up, so there is nothing to check for them. | Run `make backfill` if it has not been run since the last discover. Otherwise expected. `False` here means "no website on file or not reachable", not "site is down". |
| Registration-age columns are empty for some accounts | The lookup needs a registry number, and Google-Maps-only accounts do not have one. | Expected. A real lookup failure shows in `npi_age_error` and is retried next run. |
| Enrich was interrupted partway | Closed laptop, lost network, Ctrl-C. | Re-run `make enrich`. Progress is saved after every 20 accounts (`--batch-size` changes this), so at most one batch is lost and the run picks up where it stopped. |
| Some accounts show a value in a `<signal>_error` column after a full run | That signal failed for those accounts (timeout, service error). | Re-run `make enrich`; only failed signals are retried. To redo everything, move or delete `signals_raw.csv` first. |
| Brief or sequence run reports `error` with `credit balance is too low` | The Anthropic account behind the key has no credit. Nothing is charged for these. | Add credit to the same organization the key belongs to, then re-run; only missing items are written. |
| A brief or sequence file opens with a "check failed" banner | The draft cited no fact, used a number or a capitalised word that is not in its cited facts, or broke a length rule. | Re-run with `--redo-failed`. The check covers citations, numbers, capitalised words and length; it does not catch a wrong lowercase word or an overreaching inference, so drafts still need a human read before sending. |
| A check fails with `'<Word>' is not in the cited facts` for a word that is fine | The word is true but no cited fact contains it (for example a street-type word the model spelled out). | If it is a general word, add it to `allowed_words` in `brief.yaml`. If it is a place or name, the prompt is doing its job; re-run with `--redo-failed`. |
| Brief or sequence run reports some items "out of date" | Their facts, sources or checks changed since they were written. | Expected after re-scoring or a check change. The run rewrites them. |
| `make leak-test` prints FAIL | A real identifier from `outputs/raw/` appears in a published file. The output names the kind and the file, not the value. | Do not publish. Find the text in that file, fix the scrub in `src/anonymize.py` (never by editing the output), rebuild with `make public`, and re-run the test. |
| `make leak-test` prints FAIL for a name made of ordinary words (an account named like a category) that appears in a generic sentence | The account's name matches wording that does not identify it, for example a sentence about "licensed providers" next to an account named "Care Providers". | Find where it appears first. If it is category wording, add a row to `outputs/raw/leak_allowlist.csv` with columns `name`, `allowed_phrase`, `reason`. The phrase must contain the name plus at least one more word. Only that exact phrase, in that case, is skipped for that name; the bare name or another case still fails, and no other name is affected. The test prints how many occurrences it masked. Never allow a bare name. |
| `make check-generic` prints FAIL | A vertical-specific term is in core code or a doc. The output lists file and line. | Move the term into `config/verticals/<name>/`, or reword. |

## 6. Costs

| Item | Cost |
|---|---|
| Provider registry (discovery and the registration-age signal) | Free. No key. |
| Job-postings and website signals | Free. No key. They read the accounts' own websites. |
| Google Maps discovery | Paid, per request. |
| Google Maps backfill | Paid, one request per account missing a website. Free on re-runs (cached). |
| Briefs | Paid, on the Anthropic API. Measured on the NYC run: about $0.03 per brief. Logged per brief in `briefs_index.csv`; totals are in `outputs/public/costs.md`. |
| Sequences | Paid, on the Anthropic API. Measured on the NYC run: about $0.02 per sequence. Logged in `sequences_index.csv`; totals are in `outputs/public/costs.md`. |

A full rewrite of all 244 groups in tiers A and B costs about $13 at these rates (244 × $0.033 for briefs plus 244 × $0.019 for sequences, the per-draft costs of the 2026-10-13 first attempts, comes to $12.69). A refresh rewrites only the groups whose facts changed, so it costs less; how much less is not known yet, because no week-over-week refresh has been run. The Anthropic API is prepaid. If the balance runs out mid-run, the unfinished items are saved as `error` and the next run writes them; turning on auto-reload in the Claude Console billing settings avoids the stop.

The Google call is Places Text Search. Because the engine asks for website and phone in the same call, Google bills it at its higher "Enterprise" tier, list price roughly $35 per 1,000 requests. One NYC discovery run is 15 searches (5 place names × 3 search phrases), each up to 3 pages, so at most 45 requests: about $1.50 at list price, before any free monthly allowance.

For a new metro, estimate: number of `search_cities` × number of search phrases × 3 pages. Every re-run of discover is billed again. Enrich makes no Google calls.

Backfill is the larger cost: one request per registry-only account at the same tier. The NYC run made 1,252 lookups, about $44 at list price before any free monthly allowance. That is paid once per metro; the cache makes later runs free until new accounts appear.

**Confirm current prices on Google's Maps Platform pricing page before relying on these numbers.** Tiers and free allowances change.

## 7. What is not built yet

Built but not proven: `make refresh` and `make triggers` (the only collections are 2026-10-09 and 2026-10-12 to 2026-10-13, so there is no week-over-week run) and the Monday playbook (`docs/monday-playbook.md`, a draft no sales team has used).

No commands exist for any of these. Each is listed with what it needs in `V2.md`:

- Impact write-up with a measured time comparison
- How to re-weight the rubric once outcome data exists ("closing the loop")
- Contacts: the engine collects no people

**Dropped from v1: the objection library.** It was planned as a set of objections drawn from real conversations with operators. No such conversations have been recorded, and a library written without them would be invented, so it is left out.
