# Report card

Built 2026-10-13 from the pipeline's own output files. Signals collected: 2026-10-12 to 2026-10-13. Accounts discovered: 2026-10-12.

Measurements only: no grades, because no outcome data or human labels exist yet. The last two sections are written by hand in the vertical's evals.yaml.

## Discovery

- 1501 accounts in 1415 groups (accounts sharing a website count as one group).
- By source: NPPES: 1182, Google Maps: 181, NPPES; Google Maps: 138.
- 33.4% have a website; 99.9% have a phone number.
- Left out before scoring: outside territory (dropped by discover): 48, reviewed: 13.
- Rows fetched by source: nppes: 1759, google_maps: 361; 558 rows merged as duplicates.

## Signals

- 1501 accounts enriched. Signal errors: careers_page: 0, http_check: 0, npi_age: 0, state_license: 0.

| Signal column | Accounts with a value |
|---|---|
| `jobs_status` | 100.0% |
| `jobs_ats` | 3.3% |
| `jobs_source_url` | 18.4% |
| `jobs_total` | 1.5% |
| `jobs_total_all_locations` | 1.5% |
| `jobs_care_worker` | 1.5% |
| `jobs_scheduling_ops` | 1.5% |
| `jobs_admin_compliance` | 1.5% |
| `jobs_titles_sample` | 1.5% |
| `website_live` | 100.0% |
| `website_has_ssl` | 33.4% |
| `npi_enrolled_year` | 87.9% |
| `npi_age_years` | 87.9% |
| `license_status` | 100.0% |
| `license_types` | 35.4% |
| `license_names` | 35.4% |
| `license_match` | 35.4% |

`jobs_status` breakdown:

| Status | Accounts |
|---|---|
| no_website | 999 |
| careers_page_no_listings | 196 |
| no_careers_page | 151 |
| site_unreachable | 67 |
| ats_unsupported | 38 |
| offsite_listings | 19 |
| counted | 12 |
| listings_found | 11 |
| robots_disallowed | 8 |

`license_status` breakdown:

| Status | Accounts |
|---|---|
| not_found | 969 |
| matched | 532 |

## Scoring

The rubric weights are a hypothesis. They have not been fitted to meetings booked or deals won.

| Tier | Minimum score | Accounts | Groups | Average data coverage |
|---|---|---|---|---|
| A | 60 | 44 | 33 | 91.8% |
| B | 42 | 257 | 211 | 86.0% |
| C | 25 | 181 | 152 | 74.3% |
| D | 0 | 1019 | 1019 | 35.2% |

Data coverage is the share of the rubric judged on real data. A low score with low coverage means "could not find out", not "poor fit".

| Criterion | Max points | Average points | Accounts scoring above zero |
|---|---|---|---|
| Hiring activity | 35 | 2.6 | 28.4% |
| Back-office hiring | 10 | 0.1 | 1.5% |
| Web presence | 15 | 4.9 | 34.6% |
| Multi-site | 10 | 1.3 | 33.4% |
| Agency type | 10 | 6.5 | 99.3% |
| Maturity | 10 | 7.4 | 87.9% |
| Tech posture | 10 | 1.6 | 30.2% |

## Briefs

- 244 briefs written; 100.0% pass the source check. 0 more are out of date and are not counted or published until rewritten.
- 1570 statements, 6.4 per brief, each citing at least one numbered fact.
- 5.1 facts available per brief; 95.2% of available facts were cited.

## Sequences

- 244 sequences (732 touches); 100.0% pass their checks. 0 more are out of date and are not counted or published until rewritten.
- First-email closing questions: 84.8% are distinct; the most repeated one appears 7 times.
- Written for: Administrator (176), Director of Operations or COO (37), Owner or Operator (30), Executive Director (1).

| Touch | Word limit | Average words | Longest |
|---|---|---|---|
| 1 | 90 | 65.2 | 77 |
| 2 | 70 | 46.5 | 64 |
| 3 | 60 | 43.7 | 54 |

## First-attempt results, by prompt version

A draft as it was first written, before any re-run of one that failed. Taken from the run logs and kept by hand in a private file, because the draft files keep only the final result. The pass rates earlier in this card are after failed drafts were re-run, so they are 100%.

A later prompt version is judged by whatever checks existed when it ran, and checks were added along the way, so the rates below are not a clean comparison between prompt versions.

| Step | Prompt version | First attempts | Passed first time | Pass rate | What failed |
|---|---|---|---|---|---|
| Briefs | brief_prompt.md with the guessed-claim and shared-domain rules | 222 | 210 | 94.6% | digit not in cited facts (12) |
| Briefs | brief_prompt.md with the place-name rule | 263 | 250 | 95.1% | number word not in cited facts (4), digit not in cited facts (9) |
| Sequences | sequence_prompt.md with the guessed-claim and engine-vocabulary rules | 223 | 216 | 96.9% | digit not in cited facts (4), job title not in cited facts (3) |
| Sequences | sequence_prompt.md with the place-name rule | 244 | 229 | 93.9% | number word not in cited facts (7), digit not in cited facts (7), place name not in cited facts (1) |

- Briefs: 33 re-run attempts, 31 passed. A draft that failed twice is counted twice.
- Sequences: 29 re-run attempts, 22 passed. A draft that failed twice is counted twice.

## What changed when a check was added

Each row is the same measurement, run over the published drafts before and after a check and a prompt rule were added for it on 2026-10-13. The checks were written after a blind grading of 15 briefs by a model that had not seen the pipeline; the problems it found were not caught by any check at the time.

| Measurement | Before | After |
|---|---|---|
| guessed claims in briefs | 67 of 289 (23%) | 0 of 244 |
| engine vocabulary in outreach touches | 59 | 0 |
| raw uppercase addresses in outreach touches | 35 | 0 |

The before figures were measured with the same check definitions, applied to the drafts as they stood on 2026-10-13 before the prompt and code changes. The second prompt version was measured against stricter checks than the first, so its pass rate is not directly comparable with the first.

## What the automated checks cover (written by hand)

- Briefs: every statement cites at least one numbered fact, every cited fact exists, every number (in digits, or a number word from two up) appears in a cited fact, and every capitalised word inside a sentence (a place, an organisation, a job title) appears in a cited fact.
- Sequences: the same citation, number and wording rules, plus word limits, subject rules and allowed merge fields.
- Guessed claims: a hedge word ("suggests", "likely", "appears to") followed in the same sentence by a claim of how often something happens, that it is happening now, or who owns whom. The facts are a snapshot of public pages and cannot establish any of those.
- Outreach wording: the engine's own vocabulary (territory, account, tier, score, ranked) is rejected in any subject or body, because a draft carrying it reads as a database export.
- Saved text is re-checked on every build. A brief or sequence whose facts changed, or that fails a check added since it was written, is held back until rewritten.
- Public dataset: each published record is searched for that account's own name words, domain, phone number and IDs, and a separate leak test searches every published file for every account's identifiers. A hit fails the build.

## Not measured (written by hand)

- Whether the top tiers are actually the best accounts. No human has labelled a sample, and no meetings-booked or closed-won data exists to test the rubric against.
- Reply rates or meetings from the outreach drafts. Nothing has been sent.
- Unsupported wording in lowercase, beyond the guessed-claim patterns now checked. A wrong common word, or an inference of a kind not in the claim list, still passes. The claim list was written from one blind grading of 15 briefs, so it covers the mistakes that grading found and not necessarily others.
- Accounts that are not the target type. The rubric trusts the registry's self-reported classification, plus a match to the state licence list by name and phone. An account that trades under another name shows as not found, which is not proof it is unlicensed. Accounts flagged by name are reviewed by hand, and only those a person marks are excluded.
- Recall of discovery: how many real agencies in the territory are missing from the list.
- Job-posting accuracy. Counts were read from each employer's own job feed once and not cross-checked; most accounts have no readable feed at all.
- First-pass failure rate under the current prompts. The first attempts counted above used the prompts as they stood before the number rule was tightened on 2026-10-13. The tightened prompts have only been run on drafts that had already failed, so their own first-pass rate is not known.
- Whether the export files import cleanly. They have not been loaded into a live CRM or sales engagement workspace.
- Whether the public dataset can be re-identified. Names and contact details are removed, but an account's combination of facts may still point to it.
