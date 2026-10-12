# Report card

Built 2026-10-12 from the pipeline's own output files. Signals collected: 2026-10-09 to 2026-10-12. Accounts discovered: not recorded.

Measurements only: no grades, because no outcome data or human labels exist yet. The last two sections are written by hand in the vertical's evals.yaml.

## Discovery

- 1485 accounts in 1404 groups (accounts sharing a website count as one group).
- By source: NPPES: 1180, Google Maps: 166, NPPES; Google Maps: 139.
- 32.8% have a website; 100.0% have a phone number.
- Left out before scoring: outside territory (excluded zip): 48, reviewed: 13.

## Signals

- 1485 accounts enriched. Signal errors: careers_page: 0, http_check: 0, npi_age: 0.

| Signal column | Accounts with a value |
|---|---|
| `jobs_status` | 100.0% |
| `jobs_ats` | 3.0% |
| `jobs_source_url` | 18.2% |
| `jobs_total` | 1.5% |
| `jobs_total_all_locations` | 1.5% |
| `jobs_care_worker` | 1.5% |
| `jobs_scheduling_ops` | 1.5% |
| `jobs_admin_compliance` | 1.5% |
| `jobs_titles_sample` | 1.4% |
| `website_live` | 100.0% |
| `website_has_ssl` | 32.8% |
| `npi_enrolled_year` | 88.8% |
| `npi_age_years` | 88.8% |

`jobs_status` breakdown:

| Status | Accounts |
|---|---|
| no_website | 998 |
| careers_page_no_listings | 197 |
| no_careers_page | 145 |
| site_unreachable | 63 |
| ats_unsupported | 34 |
| offsite_listings | 18 |
| counted | 11 |
| listings_found | 11 |
| robots_disallowed | 8 |

## Scoring

The rubric weights are a hypothesis. They have not been fitted to meetings booked or deals won.

| Tier | Minimum score | Accounts | Groups | Average data coverage |
|---|---|---|---|---|
| A | 60 | 46 | 33 | 92.0% |
| B | 42 | 267 | 220 | 86.0% |
| C | 25 | 169 | 148 | 71.7% |
| D | 0 | 1003 | 1003 | 35.0% |

Data coverage is the share of the rubric judged on real data. A low score with low coverage means "could not find out", not "poor fit".

| Criterion | Max points | Average points | Accounts scoring above zero |
|---|---|---|---|
| Hiring activity | 35 | 2.5 | 28.0% |
| Back-office hiring | 10 | 0.1 | 1.4% |
| Web presence | 15 | 4.8 | 34.1% |
| Multi-site | 10 | 1.2 | 32.8% |
| Agency type | 10 | 9.5 | 99.6% |
| Maturity | 10 | 7.4 | 88.8% |
| Tech posture | 10 | 1.6 | 29.9% |

## Briefs

- 215 briefs written; 99.5% pass the source check. 38 more are out of date and are not counted or published until rewritten (facts changed: 38).
- 1285 statements, 6.0 per brief, each citing at least one numbered fact.
- 4.1 facts available per brief; 99.8% of available facts were cited.

## Sequences

- 188 sequences (564 touches); 100.0% pass their checks. 65 more are out of date and are not counted or published until rewritten (facts changed: 40, fails current checks: 25).
- First-email closing questions: 77.1% are distinct; the most repeated one appears 7 times.
- Written for: Administrator (170), Owner or Operator (17), Executive Director (1).

| Touch | Word limit | Average words | Longest |
|---|---|---|---|
| 1 | 90 | 64.9 | 76 |
| 2 | 70 | 46.7 | 60 |
| 3 | 60 | 44.6 | 51 |

## What the automated checks cover (written by hand)

- Briefs: every statement cites at least one numbered fact, every cited fact exists, every number (in digits, or a number word from two up) appears in a cited fact, and every capitalised word inside a sentence (a place, an organisation, a job title) appears in a cited fact.
- Sequences: the same citation, number and wording rules, plus word limits, subject rules and allowed merge fields.
- Saved text is re-checked on every build. A brief or sequence whose facts changed, or that fails a check added since it was written, is held back until rewritten.
- Public dataset: each published record is searched for that account's own name words, domain, phone number and IDs, and a separate leak test searches every published file for every account's identifiers. A hit fails the build.

## Not measured (written by hand)

- Whether the top tiers are actually the best accounts. No human has labelled a sample, and no meetings-booked or closed-won data exists to test the rubric against.
- Reply rates or meetings from the outreach drafts. Nothing has been sent.
- Unsupported wording in lowercase. The checks catch capitalised words and number words missing from the cited facts, but not a wrong common word or an inference that goes further than its fact.
- Accounts that are not the target type. The rubric trusts the registry's self-reported classification. Accounts flagged by name are reviewed by hand, and only those a person marks are excluded; the rest of the list has not been reviewed.
- Recall of discovery: how many real agencies in the territory are missing from the list.
- Job-posting accuracy. Counts were read from each employer's own job feed once and not cross-checked; most accounts have no readable feed at all.
- First-pass failure rates. The pass rates above are after re-running drafts that failed a check; how many failed on the first attempt is not logged.
- Whether the export files import cleanly. They have not been loaded into a live CRM or sales engagement workspace.
- Whether the public dataset can be re-identified. Names and contact details are removed, but an account's combination of facts may still point to it.
