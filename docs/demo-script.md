# Demo script

For walking someone through the territory engine live, in about five minutes. The last
section compresses it to ninety seconds for a recording.

**The one idea to land:** most people demo the part that works. The reason to hire the person
who built this is that they measured where it breaks and wrote the number down. Give the
capability two minutes and the measurement three.

Do not apologise anywhere in this. Every limit below is stated as a finding, because that is
what it is.

## Before you start

- `make site`, then open `http://localhost:8000/site/` and leave it on the Overview tab.
- A terminal in the project root, large font, cleared.
- Have `outputs/public/project_review.md` open in a tab you can switch to if asked.
- Close anything showing real account names. The site is anonymized; your editor may not be.

## 0:00 to 0:30 — what this is

> "A seller covering New York has about 1,500 home care agencies they could call and no way
> to tell which ten matter this week. This finds them from public sources, ranks them on
> public evidence, and writes the first brief and the first email. Every sentence in a brief
> cites a numbered fact with a dated link, and code checks that, not a model."

Stay on the Overview tab while you say it. Do not click yet.

## 0:30 to 1:30 — the shape of the thing

Point at the four tiles, in this order, one line each.

- **1,501 accounts in 1,415 groups.** "Two public sources, merged. Locations of one operator
  collapse into one row so a seller works an operator once, not five times."
- **33 tier A groups.** "Out of 1,415. The point of the thing is that this number is small."
- **244 briefs and sequences, 100% passing the source check.**
- **$0.03 per brief.** "The whole territory costs about thirteen dollars to rewrite."

Then the two charts. On **Groups by tier**, say the line that matters:

> "Look at coverage next to each tier. 92% for A, 35% for D. The bottom tier is mostly
> accounts we could not assess, not accounts that scored badly on evidence. Those are
> different things and the list keeps them apart."

On **Average points by criterion**, plant the seed you pay off at the end:

> "Hold on to hiring activity. It is the heaviest criterion in the rubric, 35 of 100 points.
> I will come back to it."

## 1:30 to 3:00 — one account, end to end

Click **Accounts**. Set **Sort: open roles**. Click the top row.

This is the part that earns the job. Walk the modal top to bottom.

1. **Score breakdown.** "Every point has a rule behind it in a YAML file. Nothing here is a
   model's opinion about how good the account is."
2. **Why this score.** "Plain language, generated from the same rules."
3. **Brief.** Read the headline out loud, then stop and point at the bracketed fact ids.
   > "F1, F2, F6. Those are not decoration. Code parses this sentence, pulls the facts it
   > cites, and fails the build if a number or a capitalised word in the sentence is not in
   > those facts. A model wrote the prose. It was not trusted with the facts."
4. **Facts and sources.** "Each one has a source link and the date it was collected. A seller
   can click through before a call."
5. **What we don't know.** Say this slowly.
   > "This section is written by code, not the model. It is the part most tools leave out."

Close the modal. Sort by **rank** and scroll once so they see the long tail.

> "Most of this list is agencies with no website and nothing readable. The engine says so
> rather than scoring them low and implying they are a bad fit."

## 3:00 to 4:00 — the measurement, and the honest number

Click **Report card**.

> "This is generated from the run's own output files. I do not type numbers into it."

Then go straight to the two sections that matter.

**First-attempt results, by prompt version.** "The pass rates on the site are 100% because
failed drafts get rewritten. That would be a dishonest number on its own, so the card also
prints what happened on the first try: 94.6% and 96.9% most recently, with the failure types."

**What changed when a check was added.** Let this one sit.

> "A model that had never seen this pipeline graded fifteen briefs blind. It found the drafts
> turning a snapshot into a habit. 'Runs hiring through Paycom' is a fact. 'Which suggests
> recruiting is ongoing' is a guess, and no fact supported it. That was in 23% of briefs and
> every existing check passed it, because the words are lowercase and carry no number. So I
> made it a check. It is now zero."

## 4:00 to 5:00 — the close

This is the whole demo. Slow down.

> "Three things this does not prove, and I would rather say them than have you find them.
>
> It finds 75.8% of the licensed providers the state register lists in these zip codes. One
> in four is missing, and I know that because I measured it rather than assuming it.
>
> A blind grader rated the briefs 4.5 out of 5 for accuracy and 2.1 out of 5 for usefulness.
> It would call one of the fifteen it read.
>
> And that criterion I asked you to hold on to. Hiring activity, the heaviest thing in my
> rubric, is readable for about 1.5% of accounts. I found that three separate ways: the
> weight sensitivity test, the brief grading, and a blind ranking built from outside sources.
> All three landed on the same ceiling.
>
> So what actually orders this list is licence status, years registered and web presence,
> which describe what an agency is, not why to call it this week. The plumbing is built and
> tested. The limit is the data, and the next thing I would build is more signal, not better
> prose."

Stop there. Do not fill the silence.

## Optional 60 seconds: the terminal

Worth doing if they are technical, and strong if they look sceptical of the citation claim.

```
make checks
```

Three things pass: no vertical-specific term in core code, 132 tests, and a leak test that
searches every published file for 2,528 real names, 1,410 addresses, 1,513 phone numbers and
1,833 identifiers.

> "A new vertical is a config folder. The check that nothing vertical leaked into the core is
> a test, not a promise."

If you want the sharpest version, open a brief that failed a check and show the banner at the
top of the file: the engine saves a failing draft with the reason and refuses to publish it.

## The ninety-second version, for a recording

Cut to four beats. No terminal.

1. **0:00** The problem sentence, on the Overview tab.
2. **0:15** The four tiles, one breath. Then: "Look at coverage next to each tier. The bottom
   tier is what we could not assess, not what scored badly."
3. **0:35** One account open. The bracketed fact ids and the "What we don't know" section.
   "A model wrote the prose. It was not trusted with the facts."
4. **1:05** The close, trimmed to: 75.8% recall, 2.1 out of 5 usefulness, and the heaviest
   criterion readable for 1.5% of accounts, found three ways. "The limit is the data, not the
   writing."

End on the honest number, not on a feature.

## Questions you should expect

**"Why should I believe the citation check does anything?"**
Show it. Open a draft that failed and read the banner. Then: two of the five checks exist only
because a blind grading found the problem first, so I expect a sixth is missing.

**"Your pass rates are 100%. That seems convenient."**
They are after retries, and the report card says so and prints the first-attempt rate beside
them. 94.6% for briefs, 96.9% for sequences, with the failure types per prompt version.

**"How do you know the ranking is any good?"**
I do not, and nothing in the project claims it. There is no outcome data. What I can show is
that it is not fragile, halving any single weight keeps 91 to 100% of the same-sized top
group, and that two blind checks agree with the coarse order. Both read the same facts the
rubric reads, so neither is independent the way a person would be.

**"Would a seller actually use these briefs?"**
On this evidence, for most accounts, no. That is a data problem, not a prompt problem. The one
account with a live open role was the one the grader said it would call.

**"How long would a second city take?"**
A metro is a config file, a vertical is a config folder, and a check enforces that no vertical
term reaches the core. I have not done a second one, so that is designed for and not
demonstrated. The honest blocker is that output goes to one fixed folder today, so a second
metro would overwrite the first. That is written down.

**"What would you build next?"**
Signal, not prose. Readable open roles with titles and posting dates, week over week movement,
and licence effective and expiry dates rather than a registry enrollment year. Usefulness is
capped at 1.5% readable hiring data, so better writing cannot move it.
