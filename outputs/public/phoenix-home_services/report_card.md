# Report card

Built 2026-10-22 from the pipeline's own output files. Signals collected: 2026-10-22. Accounts discovered: 2026-10-22.

Measurements only: no grades, because no outcome data or human labels exist yet. The last two sections are written by hand in the vertical's evals.yaml.

## Discovery

- 137 accounts in 130 groups (accounts sharing a website count as one group).
- By source: Google Maps: 137.
- 94.2% have a website; 99.3% have a phone number.
- Left out before scoring: none.
- Rows fetched by source: google_maps: 138; 1 rows merged as duplicates.

## Signals

- 137 accounts enriched. Signal errors: careers_page: 0, http_check: 0.

| Signal column | Accounts with a value |
|---|---|
| `jobs_status` | 100.0% |
| `jobs_ats` | 9.5% |
| `jobs_source_url` | 33.6% |
| `jobs_total` | 4.4% |
| `jobs_total_all_locations` | 4.4% |
| `jobs_call_handling` | 4.4% |
| `jobs_technician` | 4.4% |
| `jobs_office_admin` | 4.4% |
| `jobs_titles_sample` | 4.4% |
| `website_live` | 100.0% |
| `website_has_ssl` | 94.2% |

`jobs_status` breakdown:

| Status | Accounts |
|---|---|
| no_careers_page | 54 |
| careers_page_no_listings | 30 |
| site_unreachable | 28 |
| ats_unsupported | 10 |
| no_website | 8 |
| counted | 3 |
| listings_found | 3 |
| robots_disallowed | 1 |

## Scoring

The rubric weights are a hypothesis. They have not been fitted to meetings booked or deals won.

| Tier | Minimum score | Accounts | Groups | Average data coverage |
|---|---|---|---|---|
| A | 60 | 3 | 3 | 100.0% |
| B | 42 | 14 | 12 | 76.4% |
| C | 25 | 94 | 89 | 66.5% |
| D | 0 | 26 | 26 | 37.3% |

Data coverage is the share of the rubric judged on real data. A low score with low coverage means "could not find out", not "poor fit".

| Criterion | Max points | Average points | Accounts scoring above zero |
|---|---|---|---|
| Call-handling hiring | 30 | 0.3 | 4.4% |
| Hiring activity | 25 | 4.2 | 73.0% |
| Multi-site | 15 | 3.5 | 94.2% |
| Web presence | 10 | 8.9 | 100.0% |
| Business type | 10 | 8.9 | 98.5% |
| Tech posture | 10 | 4.9 | 90.5% |

## Briefs

- 15 briefs written; 93.3% pass the source check. 0 more are out of date and are not counted or published until rewritten.
- 85 statements, 5.7 per brief, each citing at least one numbered fact.
- 4.0 facts available per brief; 98.3% of available facts were cited.

## Sequences

- 15 sequences (45 touches); 100.0% pass their checks. 0 more are out of date and are not counted or published until rewritten.
- First-email closing questions: 93.3% are distinct; the most repeated one appears 2 times.
- Written for: Owner or General Manager (9), Operations Manager (6).

| Touch | Word limit | Average words | Longest |
|---|---|---|---|
| 1 | 80 | 53.3 | 67 |
| 2 | 60 | 39.7 | 48 |
| 3 | 60 | 46.0 | 51 |

## What the automated checks cover (written by hand)

- Briefs: every statement cites at least one numbered fact, every cited fact exists, every number appears in a cited fact, and every capitalised word inside a sentence appears in a cited fact.
- Sequences: the same citation, number and wording rules, plus word limits, subject rules and allowed merge fields.
- Guessed claims: a hedge word followed in the same sentence by a claim of frequency, timing, ownership, or how calls are answered today (missed calls, voicemail).
- Outreach wording: the engine's own vocabulary (territory, account, tier, score, ranked) is rejected in any subject or body.
- Public dataset: each published record is searched for that business's own name words, domain, phone number and IDs, and the leak test searches every published file for every business's identifiers.

## Not measured (written by hand)

- Whether the top tiers are the best prospects. No human has labelled a sample and no outcome data exists for this vertical.
- Recall of discovery. There is no public register of these contractors to measure against; the list is whatever three Google Maps searches for one city returned, capped at 60 results each.
- Whether a contractor's Google Maps category is right. It is chosen by the business.
- Call volume, answer rate, or how calls are handled today. No public source shows them.
- Job-posting accuracy. Counts were read from each contractor's own careers page once and not cross-checked.
- Reply rates. Nothing has been sent.
