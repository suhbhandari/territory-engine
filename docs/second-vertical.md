# Second vertical: residential home services

The claim being tested: **a new vertical is a config folder, not new code.** This records what it actually took to add a second one: residential HVAC, plumbing and electrical contractors in Phoenix, for a generic AI phone answering and booking product. Built 2026-10-21 to 2026-10-22.

## The result in one paragraph

The vertical itself needed **no core code changes**. Discovery, enrichment, scoring, briefs, sequences, exports, the public build and the report card all ran on a new `config/verticals/home_services/` folder and a new `config/metro/phoenix.yaml`. Getting there needed two changes to core code first, both already listed in `V2.md` as blockers: the public build and the site read the first vertical's signal columns by name (#15), and every run wrote to one fixed folder (#16). Those touched 19 core files (18 changed, 1 new), most by a two-line import change. Running the new vertical also exposed an anonymization bug that had been live in the first vertical's public data.

## Core files that changed, and why

### Before the vertical: the public build named signal columns (V2 #15)

| File | Change |
|---|---|
| `src/anonymize.py` | Published fields (type, years registered, hiring status, hiring system, open roles) were read from fixed column names. Now each vertical's `public.yaml` lists which columns to publish, under what name, and whether each is copied, banded into ranges or hidden. Values hidden in text (the hiring system) and columns treated as ordinary language also come from config. |
| `site/index.html` | The account table, filter, sort options, status labels, anonymization note and two "how it works" lines were written for the first vertical. They now come from `public.yaml` through `site_data.js`. Checked: the first vertical's public data was identical before and after, and the page script renders the same table. |

### Before the vertical: one fixed output folder (V2 #16)

| File | Change |
|---|---|
| `src/paths.py` (new) | One place that says where a run's files live. No run named: `outputs/raw/` and `outputs/public/`, as before. `RUN=<name>`: `outputs/raw/<name>/` and `outputs/public/<name>/`. |
| `Makefile` | A `RUN` variable, passed to every step. |
| `src/discover.py`, `backfill.py`, `enrich.py`, `score.py`, `brief.py`, `sequence.py`, `export.py`, `anonymize.py`, `evals.py`, `triggers.py`, `exclusions.py`, `push_hubspot.py`; `scripts/snapshot.py`, `recall_check.py`, `tier_stability.py` | Each built its own `outputs/raw` path. Each now imports it from `src/paths.py`. No other change. This also removes the duplicated path constants listed in V2 #22. |
| `scripts/leak_test.py` | Runs now publish side by side, so the test checks every run's private identifiers against every published file. It also stopped naming one signal column (`jobs_source_url`); it now reads any signal column ending in `_url`. |

### During the vertical

| File | Change |
|---|---|
| `scripts/check_generic.py` | The second vertical's terms (HVAC, plumber, electrician, dispatcher, contractor, technician, answering service, home services) added, so they cannot slip into core code. This is the rule working as intended, not a gap. The phase spec and this write-up are excluded because they have to name the vertical. |
| `src/anonymize.py` | **A bug, found here, live in the first vertical too.** The step that turns counts in text into ranges also turned the alias's own number into a range: "I saw Account 0001 has 7 open roles" was published as "Account 1-4 has 5-19 open roles". The first vertical's published data had 5 of these. A count followed by "located" ("all 7 located in AZ") was also left exact. Both fixed and tested; both public builds rebuilt. |

Tests added: `tests/test_anonymize.py` (published fields follow config; alias numbers are not banded) and `tests/test_leak_test.py` (a second run's identifiers are checked against every published file; the snapshot folder is not a run).

### Config only: what the vertical is

`config/verticals/home_services/`: `discovery.yaml` (three Google Maps searches, non-contractor place types dropped, listing sites that are not a business's own website), `signals.yaml` (the existing careers-page and website-check modules, with job titles sorted into call-handling, technician and office buckets), `rubric.yaml`, `personas.yaml`, `brief.yaml`, `brief_prompt.md`, `sequence.yaml`, `sequence_prompt.md`, `seller_context.md`, `glossary.yaml`, `triggers.yaml`, `public.yaml`, `export.yaml`, `evals.yaml`. Plus `config/metro/phoenix.yaml`.

One config fix after the first look at the data: Google Places has no HVAC category, so HVAC shops come back as "General Contractor" (40 of 47 had a heating or air word in the name). The rubric now gives 8 of 10 points when the business name names the trade, so HVAC companies are not scored below plumbers because of how Google files them.

## The run

Phoenix only, three searches, 2026-10-22. Full numbers in `outputs/public/phoenix-home_services/report_card.md`.

| Measure | Result |
|---|---|
| Accounts | 137 in 130 groups (138 fetched, 1 merged) |
| Tiers (accounts / groups) | A 3 / 3, B 14 / 12, C 94 / 89, D 26 / 26 |
| Average data coverage | 62.7% (A 100%, B 76%, C 67%, D 37%) |
| Website on file | 94.2% |
| Readable job count | 6 of 137 (4.4%). 54 have no careers page, 30 a page with no readable listings, 28 a site the check could not read, 10 a hiring system with no readable feed |
| Briefs | 15 written; 13 passed first time; after re-runs 14 pass (93.3%) and 1 is held back. It failed three times on the same rule: it wrote "Google Maps" in a sentence that cited a different fact |
| Sequences | 15 written; 14 passed first time; 15 of 15 after one re-run. The failure was a plumber's call opener that mentioned HVAC |
| Personas used | Owner or General Manager 9, Operations Manager 6, Call Center Manager 0 |
| Cost | Google: up to 9 Text Search requests, about $0.32 (estimate, before any free allowance). Model: $0.95 including re-runs |
| Leak test | PASS across both runs |

**What this shows about the vertical, not the engine:** the main "needs help now" signal (dispatch and customer service hiring) is nearly empty. Only 6 contractors publish a job feed the engine can read, and 1 of them is hiring a dispatch or customer service role. So the ranking here mostly rests on web presence, business type and shared domains. That is a finding about where these businesses post jobs (job boards, not their own sites), and it is the first thing to fix before trusting this list.

**Cut line:** not needed. The run used about 140 accounts, and briefs were written for tiers A and B.

## Time

About 3.5 hours of the 6-hour box: 1.25 hours on #15 and #16 (box: 2), 1 hour writing the vertical's config, 0.5 hours running it (enrich took minutes, not the hour the first vertical's registry signals need), and the rest on the anonymization bug, checks and this write-up.

## What a third vertical would still need

- **A page for each run.** The site shows the shipped run only. A named run's public files and report card exist in `outputs/public/<run>/`, but nothing displays them. Needs the site to take a run name.
- **Typing `RUN`, `VERTICAL` and `METRO` on every step.** Forgetting `RUN` on one step reads or writes the shipped run's files. A run name could be derived from the metro and vertical, or saved once per run.
- **Signals for businesses that do not post jobs on their own site.** Both verticals lean on careers pages, and both found few readable ones (1.5% and 4.4%). A job-board source, or review counts and ratings from Maps, would be new generic code. The Maps source does not request review counts today, so that is a source change, not config.
- **A way to check category quality before scoring.** The HVAC problem was found only by reading the output. A report of the categories discover returned, by count, printed before scoring, would catch it.
- **Its own `check_generic.py` terms, `public.yaml` and `export.yaml`** (including a `hubspot:` block if it will be pushed; this vertical has none).
- **A recall measure, if one exists.** The first vertical has a state register to count against. This one has none that was checked; Arizona's contractor licence records might serve through the existing `open_data_match` signal if they are published in a usable form, which has not been looked at.
