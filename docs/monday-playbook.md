# Monday playbook

How a rep uses the engine's output each week. Fifteen minutes on Monday morning, then the
week's outreach. Written for the shipped setup (Salesforce and Outreach exports); swap in
your own tools where they differ.

**Status: a proposed routine, not yet used by a sales team.** The steps match what the
engine produces today. Nobody has run this routine for a real week yet.

## Before Monday (ops, about an hour, unattended)

1. Run `make refresh` (weekly) or `make fresh` (monthly, re-finds accounts). It keeps a copy
   of last week's run, re-checks every signal, re-scores, writes the trigger list, rewrites
   only the briefs and sequences whose facts changed, rebuilds the exports and runs the checks.
2. If `make checks` prints FAIL, stop. Do not import anything until it passes.
3. Import `outputs/raw/exports/salesforce_accounts.csv` (update existing accounts by
   Territory Engine ID) and `outreach_accounts.csv` (see `docs/stack-fit.md`).

## Monday, 15 minutes

1. **Open the trigger list** (`outputs/raw/triggers.csv`, sorted best rank first). Look only at
   accounts now in tier A or B. These are the reasons to act this week:
   - a tier moved up, or a hiring change (new open roles, a careers page or hiring system appeared)
   - a new account in tier A or B
   Read the `because` column on tier changes. If the only thing that moved is a rubric
   criterion that was edited this week, it is not news about the account.
2. **Pick this week's list.** Up to 15 groups: every triggered tier A group, then triggered
   tier B groups, then untouched tier A groups by rank. Work one group (one operator), not
   each location.
3. **Skip** anything marked out of date, any account with `data_coverage` under 0.5 unless a
   trigger names it, and any account the CRM shows as already in an active conversation.

## For each account, about 3 minutes before the first touch

1. Read the brief: headline, why now, opening angle, and **what we don't know**.
2. Click the source for any fact you will repeat. Facts carry the date they were checked;
   anything older than two weeks gets a fresh look on the source page.
3. Find the person. The engine does not supply contacts: use the "Write To Role" column to
   search your contact tool, and confirm the person is current.
4. Open the sequence in Outreach, read every touch, and edit anything that does not sound
   like you. The engine's checks cover citations, numbers, capitalised names and length,
   not tone or a wrong common word.

## During the week

- Send touch 1 (email) on day 1, touch 2 (reply in thread) on day 4, call on day 7.
- Log every reply, meeting and "not a fit" against the Territory Engine ID in the CRM.
  Those outcomes are what will one day test the rubric (see `V2.md`, "Closing the loop").
- If a fact turns out to be wrong, note the account and the fact. A wrong fact is a bug in
  a source or a check, and is fixed in code, not by editing the brief.

## Friday, 5 minutes

- Count: accounts worked, touches sent, replies, meetings, wrong facts found.
- Anything that looked like a non-target account: add it to `outputs/raw/exclusions.csv`
  with a reason, so next week's run leaves it out.
