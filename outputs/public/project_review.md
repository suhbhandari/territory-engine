# Project review

A review of the territory engine, written 2026-10-13 against the run collected 2026-10-12 to 2026-10-13. Every number here comes from a file in the repository or a command in the Makefile, and each row says which. No account names appear in this file.

## Verdict

The engine does what it says mechanically: it finds 1,501 accounts in one metro from two public sources, scores them against a written rubric where every point has a reason, and writes 244 briefs and 244 outreach sequences in which every statement cites a numbered, dated fact, with code rather than a model enforcing that. The checks are real, they fail builds, and a blind grading by a model that had never seen the pipeline found two classes of error the checks could not see, which were then turned into checks of their own. What the project does not yet show is that any of this helps someone sell. The ranking has never been compared with a meeting booked or a deal won, nothing has been sent, no file has been imported into a live system, and the one quality measure that exists says the briefs are accurate but thin: a blind grader rated their usefulness 2.1 out of 5 and would contact 1 of 15 accounts this week. The honest summary is that the plumbing is built and tested, the judgment layer is untested, and the data available in public sources is not yet rich enough to make most of these briefs worth a seller's time.

## Scorecard

The original brief's wording for the goals was lost when an earlier working session ran out of context. The goals below are restated from the project's own README, CLAUDE.md and V2.md. The KPI rows are the ones the brief named.

### Goals

| # | Goal | Status | Number and evidence | Next step |
|---|---|---|---|---|
| 1 | Find the target accounts in a territory from public sources | PARTIALLY MET | 1,501 accounts in 1,415 groups from 2 sources; 2,120 rows fetched, 558 merged as duplicates, 48 dropped outside the territory, 13 removed by review. `outputs/public/report_card.md`. How many were missed is unknown. | `make recall`, which compares the list against a public register meant to be complete for the territory. Written and tested, not yet run: it needs network access to that register. |
| 2 | Rank them by public evidence of need, with a reason for every point | PARTIALLY MET | 33 tier A and 211 tier B groups. Ranking is stable: halving or raising any one criterion's weight by half keeps 91 to 100% of the same-sized top group, and weighting every criterion equally still keeps 86.1% (`make stability`). A blind grader's usefulness rating correlates 0.81 and 0.82 with the score across two separate gradings. | Compare the tiers with a real outcome. Nothing else closes this. |
| 3 | Write a source-cited brief for every top account | MET for the mechanism, NOT MET for value | 244 briefs, 1,570 statements, every one citing a numbered fact, 100% passing the source check; 95.2% of available facts were used. Blind grading of 15 rated accuracy 4.5 of 5 and usefulness 2.1 of 5. | The ceiling is the data, not the writing. See "What would raise the usefulness score". |
| 4 | Draft outreach built on the same facts | MET for the mechanism, PARTIALLY MET for quality | 244 sequences, 732 touches, 100% passing citation, number, wording, length and merge-field checks; 84.8% of first-email closing questions are distinct. Blind grading rated them 4.0 of 5 for accuracy and 3.3 of 5 for sendability. | A seller rewrites 5 drafts by hand; compare what they change. |
| 5 | Hand off to a CRM and a sequencing tool | PARTIALLY MET | 482 account rows and 244 outreach rows written with a documented field map (`docs/stack-fit.md`). Neither file has been imported anywhere. | Import both into a free developer sandbox and record what breaks. |
| 6 | Work for another vertical or metro without new code | NOT MEASURABLE YET | `make check-generic` passes: no vertical term appears in core code or docs. One vertical and one metro exist, so the claim is designed for and not demonstrated. Output also goes to one fixed folder, so a second metro would overwrite the first (V2 item 16). | Add a second vertical config and record which core files had to change. |
| 7 | Publish a demo without exposing an account | MET, with one limit stated | 8 published files scanned for 2,528 names, 1,410 addresses, 1,513 phones, 674 URLs, 438 domains and 1,833 IDs: 0 leaks (`make leak-test`). Counts are published as ranges and each account's hiring system is hidden. | Whether a combination of published facts identifies an account has not been tested. |

### KPIs

| KPI | Status | Number and evidence | Next step |
|---|---|---|---|
| Coverage and data quality | PARTIALLY MET | 1,501 accounts enriched with 0 errors across all 4 signals. Average data coverage 50.2%, but it splits hard: 91.8% in tier A against 35.2% in tier D. 33.4% have a website at all, and only 1.5% have a readable open-role count. `outputs/public/report_card.md`. | More sources, or accept that most of the territory cannot be assessed and say so on the list. |
| Scoring distribution and stability | MET | Tier A 33 groups, B 211, C 152, D 1,019. Stability measured across 15 weight changes: 86.1% to 100% of the same-sized top group is kept. `make stability`, saved to a private CSV. | None. This is measured. |
| Draft pass rates and failure types, by prompt version | MET | Per prompt version, first attempt: briefs 95.1% then 94.6%; sequences 93.9% then 96.9%. Failure types are counted per version in the report card. Later versions were judged by stricter checks, so the versions do not compare cleanly, and the card says so. | Log the prompt version per item in the draft index, so this stops being kept by hand (V2). |
| Safety | PARTIALLY MET | 0 leaks across every published file. 132 tests pass. One reviewed phrase is allowed in the leak test, recorded with its reason, and only that exact phrase in that exact case. Re-identification from combined facts is untested. | Have someone try to identify one published account from the site alone. |
| Efficiency and cost | MET | $0.034 per brief and $0.021 per sequence, measured from logged token usage. A full rewrite of all 244 groups costs about $12.69. Discovery about $1.50 per run; the one-time website backfill was 1,252 lookups, about $44, cached so re-runs are free. `outputs/public/costs.md`. | None. This is measured. |
| Freshness | PARTIALLY MET | Two collections: 2026-10-09 and 2026-10-12 to 2026-10-13, with a fresh discovery between them. The difference produced 140 trigger rows: 94 accounts changed, 31 new, 15 gone (`make triggers`). `make refresh` exists. No week-over-week refresh has been run, so how often an account changes tier is unknown. | Run `make refresh` once a week for three weeks. |
| Runbook usable by someone else | NOT MEASURABLE YET | Nobody other than the author has run it. The runbook documents every command, a failure table and costs. | Give it to one person with the keys and count the places they get stuck. |
| Generalization | NOT MEASURABLE YET | See goal 6. | See goal 6. |
| Time saved per seller | NOT MEASURED, and not claimed | No timed comparison against a person was done, so no time figure appears anywhere in the project. What is measured instead: the engine opens 3.6 distinct source pages per account and extracts 4.9 dated facts, at 5.1 cents per account. That is steps and cost, not time. | A person times 3 accounts by hand and 3 with a brief. About 40 minutes. |

## What the blind grading found

Fifteen briefs and their drafts were graded twice by a model that had not seen the pipeline, with tiers and scores hidden. Between the two rounds, two checks and three prompt rules were added in response to the first round's findings, and every draft was rewritten.

| Dimension | Round 1 | Round 2 | Change |
|---|---|---|---|
| Brief accuracy | 3.67 | 4.47 | +0.80 |
| Brief usefulness | 2.60 | 2.13 | -0.47 |
| Draft accuracy | 3.93 | 4.00 | +0.07 |
| Draft sendability | 3.07 | 3.33 | +0.27 |
| Would contact this week | 1 of 15 | 1 of 15 | no change |

**Read the usefulness row first, because it is the finding that matters.** Usefulness went down. The first round's briefs partly earned their usefulness by overclaiming: an applicant-tracking system detected on a careers page became "recruiting is an ongoing part of its operations", which no fact supported. Removing the overclaim removed the apparent reason to call, and what was left is what the public data actually supports, which is thin. The engine was not made worse. It was made honest, and honesty revealed the real ceiling.

Two caveats that cut against these numbers. The accuracy and sendability wording in the round 2 instructions named the specific faults that had just been fixed, so those two rows are not a clean comparison and are expected to rise. The usefulness wording was identical in both rounds, which is why it is the row to trust. And both rounds were graded by a model of the same family that wrote the drafts, with 15 items and one grader, so this is a weak measure of quality in absolute terms.

One result did replicate independently: in both rounds the grader's usefulness rating correlated 0.81 and 0.82 with the rubric's score, and tier A briefs outscored tier B on every dimension. That is the only evidence in the project that the ranking orders accounts the way a reader would.

## What changed when a check was added

| Measurement | Before | After |
|---|---|---|
| Briefs claiming a frequency or ownership their facts cannot support | 67 of 289 (23%) | 0 of 244 |
| Outreach touches using the engine's own vocabulary (territory, account, tier, score) | 59 | 0 |
| Outreach touches containing a raw uppercase registry address | 35 | 0 |

None of these were caught by the citation check, the number check or the capitalised-word check, because the words are lowercase and carry no number. They were found by reading the output, which is the general lesson: every check in this project was added after something got through.

## Top 5 fixes before sending this to anyone

1. **Run `make recall`.** Until it runs, the project can show that every account it lists is real and can say nothing about what it missed. That is the first question a technical reader asks, and it is one command away.
2. **Say the usefulness number out loud, in the README.** A reader who opens three briefs will notice that most of them say "has a careers page, contents unreadable". Stating 2.1 of 5 first, with the reason, is far stronger than being caught by it.
3. **Import both export files into a free sandbox.** "Mapped for Salesforce and Outreach" is currently a claim about a CSV's column names. One afternoon turns it into a demonstrated import.
4. **Tighten the licence match.** An exact name match ignores the zip, so a brand name can pull in one franchisee's licence for another location. It affects 6 of the 244 top-tier groups and it feeds the score.
5. **Give the runbook to one other person** with the keys and watch where they stop. Every "reusable" claim in the project rests on a document only its author has followed.

## What this project does not prove

- **That the ranking is right.** No meeting, reply or deal exists to test it against. The weights are one person's judgment and are labelled as such in the rubric.
- **That the briefs help anyone sell.** The only quality evidence is a model grading itself: 2.1 of 5 for usefulness, 1 of 15 worth contacting this week.
- **That it saves time.** No timed comparison against a person was done, so no time claim is made anywhere.
- **That discovery is complete.** Recall is unmeasured until `make recall` runs.
- **That the exports work.** Nothing has been imported into a live system, and nothing has been sent.
- **That it generalizes.** One vertical, one metro. The generic-code check passes, which shows discipline, not portability. A second metro would currently overwrite the first.
- **That the public demo cannot be re-identified.** Identifiers are removed and counts are banded, but no one has tried to break it.
- **That the drafts are safe to send unread.** They are built for a person to review, and the checks cover citations, numbers, capitalised words, guessed claims and the engine's own vocabulary. They do not catch a wrong ordinary word or an inference of a kind not yet on the list.

## What would raise the usefulness score

The blind grader was asked what would have to change about the data, not the writing. Its answer matches what the signal coverage shows: enrollment dates, a licence-type code and the name of an applicant-tracking system are static attributes shared by hundreds of agencies, so every brief opens the same way. Usefulness needs facts that differentiate and that change: readable open-role detail with titles and posting dates, week-over-week movement, licence effective and expiry dates rather than a registry enrollment year, and named people. Today 1.5% of accounts have a readable open-role count, and that number is the ceiling on how many briefs can have a real reason to call.

## Three questions a reviewer will ask, and honest answers

**"Your checks all pass at 100%. What do they actually catch?"**

They catch a statement with no citation, a number or a capitalised word that is not in the facts it cites, a guessed claim about frequency or ownership, the engine's own vocabulary in outreach, and length and merge-field rules. The 100% figure is after failed drafts are re-run, which is why the report card also prints the first-attempt rate per prompt version: 94.6% and 96.9% most recently. What they do not catch is a wrong ordinary lowercase word, or an inference of a kind nobody has thought of yet. Two of the five checks exist only because a blind grading found the problem first. I would expect a third to be missing.

**"Would a seller actually use these briefs?"**

On the current evidence, for most accounts, no. A blind grader rated usefulness 2.1 of 5 and would contact 1 of the 15 it read. That is not a prompt problem. Only 1.5% of accounts have a readable count of open roles, so for most of the list the strongest fact available is that a careers page exists. The format works where the data is there: the single account with a live open role was the one the grader would call. The fix is more and better signals, not better writing, and I would rather say that than ship a brief that sounds compelling because it overstates what it knows.

**"How do you know your tiers are better than sorting by company size?"**

I do not, and nothing in the project claims it. There is no outcome data, so the weights are an untested hypothesis and the rubric says so in a comment. What I can show is two things. The ranking is not fragile: changing any one criterion's weight by half in either direction keeps 91 to 100% of the same-sized top group, and even weighting every criterion equally keeps 86.1%, so the result is driven more by which accounts have evidence at all than by my particular weights. And in two separate blind gradings, the grader's usefulness rating correlated 0.81 and 0.82 with the score, and tier A beat tier B on every dimension. That is weak, correlational, and graded by a model rather than a person, but it is evidence rather than assertion.

## How to check any number in this review

| Claim | Command or file |
|---|---|
| Account, group, tier, coverage and cost figures | `outputs/public/report_card.md` and `outputs/public/costs.md`, both generated from the run's own files |
| Ranking stability | `make stability` |
| What the published files were searched for | `make leak-test` |
| Tests | `make test` (132) |
| No vertical term in core code | `make check-generic` |
| What changed between the two collections | `make triggers` |
| First-attempt pass rates and the before and after measurements | the "First-attempt results" and "What changed when a check was added" sections of the report card |
| Blind grading scores | private files, since the grading sheets carry real account names |
