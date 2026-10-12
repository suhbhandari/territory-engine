# Report card

Generated 2026-10-12 from the pipeline's own output files. Measurements only: no grades, because no outcome data or human labels exist yet.

## Discovery

- 1497 accounts in 1414 groups (accounts sharing a website count as one group).
- By source: NPPES: 1191, Google Maps: 167, NPPES; Google Maps: 139.
- 34.0% have a website; 100.0% have a phone number.
- Left out before scoring: outside territory (excluded zip): 48, reviewed: 1.

## Signals

- 1497 accounts enriched. Signal errors: careers_page: 0, http_check: 0, npi_age: 0.

| Signal column | Accounts with a value |
|---|---|
| `jobs_status` | 100.0% |
| `jobs_ats` | 3.0% |
| `jobs_source_url` | 18.7% |
| `jobs_total` | 1.5% |
| `jobs_total_all_locations` | 1.5% |
| `jobs_care_worker` | 1.5% |
| `jobs_scheduling_ops` | 1.5% |
| `jobs_admin_compliance` | 1.5% |
| `jobs_titles_sample` | 1.4% |
| `website_live` | 100.0% |
| `website_has_ssl` | 34.0% |
| `npi_enrolled_year` | 88.8% |
| `npi_age_years` | 88.8% |

`jobs_status` breakdown:

| Status | Accounts |
|---|---|
| no_website | 988 |
| careers_page_no_listings | 205 |
| no_careers_page | 156 |
| site_unreachable | 65 |
| ats_unsupported | 34 |
| offsite_listings | 19 |
| counted | 11 |
| listings_found | 11 |
| robots_disallowed | 8 |

## Scoring

The rubric weights are a hypothesis. They have not been fitted to meetings booked or deals won.

| Tier | Minimum score | Accounts | Groups | Average data coverage |
|---|---|---|---|---|
| A | 60 | 46 | 33 | 92.0% |
| B | 42 | 283 | 234 | 86.0% |
| C | 25 | 175 | 154 | 71.7% |
| D | 0 | 993 | 993 | 35.0% |

Data coverage is the share of the rubric judged on real data. A low score with low coverage means "could not find out", not "poor fit".

| Criterion | Max points | Average points | Accounts scoring above zero |
|---|---|---|---|
| Hiring activity | 35 | 2.6 | 29.1% |
| Back-office hiring | 10 | 0.1 | 1.4% |
| Web presence | 15 | 5.0 | 35.2% |
| Multi-site | 10 | 1.3 | 33.5% |
| Agency type | 10 | 9.5 | 99.6% |
| Maturity | 10 | 7.4 | 88.8% |
| Tech posture | 10 | 1.6 | 31.0% |

## Briefs

- 206 briefs written; 100.0% pass the source check. 61 more are out of date and are not counted or published until rewritten (facts changed: 42, fails current checks: 19).
- 1228 statements, 6.0 per brief, each citing at least one numbered fact.
- 4.0 facts available per brief; 99.8% of available facts were cited.

## Sequences

- 197 sequences (591 touches); 100.0% pass their checks. 70 more are out of date and are not counted or published until rewritten (facts changed: 42, fails current checks: 28).
- First-email closing questions: 77.2% are distinct; the most repeated one appears 7 times.
- Written for: Administrator (177), Owner or Operator (18), Executive Director (2).

| Touch | Word limit | Average words | Longest |
|---|---|---|---|
| 1 | 90 | 64.9 | 76 |
| 2 | 70 | 46.6 | 60 |
| 3 | 60 | 44.6 | 53 |

## What the automated checks cover

- Briefs: every statement cites at least one numbered fact, every cited fact exists, and every number written in digits appears in a cited fact.
- Sequences: the same citation and number rules, plus word limits, subject rules and allowed merge fields.
- Public dataset: each published record is searched for that account's own name words, domain, phone number and IDs; a hit fails the build.

## Not measured

- Whether the top tiers are actually the best accounts. No human has labelled a sample, and no meetings-booked or closed-won data exists to test the rubric against.
- Reply rates or meetings from the outreach drafts. Nothing has been sent.
- Unsupported wording that is not a number. A brief or email can add a detail from the model's own knowledge (a neighbourhood name, for example) or spell a number out in words, and the checks will not catch it.
- Non-agencies in the list. The rubric trusts the registry's self-reported classification; at least one pest-control company registered as in-home supportive care sits in tier B.
- Recall of discovery: how many real agencies in the territory are missing from the list.
- Job-posting accuracy. Counts were read from each employer's own job feed once and not cross-checked; most accounts have no readable feed at all.
- First-pass failure rates. The pass rates above are after re-running drafts that failed a check; how many failed on the first attempt is not logged (it was a handful per run of 276).
- Whether the export files import cleanly. They have not been loaded into a live CRM or sales engagement workspace.
- Whether the public dataset can be re-identified. Names and contact details are removed, but an account's combination of facts may still point to it.
