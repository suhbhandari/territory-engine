# Spec: ship week (Phase 10)

**How to start a Claude Code session on this:** "Read CLAUDE.md, V2.md and docs/spec-ship-week.md. Work the items in order, P0 first. Stop at each checkpoint and show me the result before moving on. Respect the timeboxes: if an item runs past its box, stop, tell me, and we cut to its cut line."

This is a new phase, not polish on an old one. It has two goals:

1. Put the engine on GitHub as a public repo with a live demo, safely.
2. Close the gaps a hiring manager will ask about first. The README already names them: the exports have never been loaded into a live CRM, there is no week-over-week refresh, there is only one vertical, and no person has graded the briefs.

Budget: about 16 hours over 2 days. Claude Code builds; Suhaani reviews, grades and records.

The CLAUDE.md rules still apply. `make check-generic` must pass at every checkpoint, and nothing vertical-specific goes into core code.

---

## P0. Publish safely (1.5 hours)

**Before the first push:**
- Run `make checks` (check-generic, tests, leak test). All pass.
- `git ls-files` lists nothing under `outputs/raw/` or `outputs/private/`, and no `.env`.
- Search the full history, not just the current tree. Neither command may print anything:
  - `git log --all --name-only --format= | grep -E '^outputs/(raw|private)/|^\.env$'`
  - `git log --all -p | grep -E 'sk-ant-|AIza[0-9A-Za-z_-]{20,}'`
  If either prints anything, stop. The history has to be rewritten before publishing, and Suhaani decides how.

**Publish:**
- Create a public GitHub repo named `territory-engine`. The local folder name can stay.
- Push `main`.
- Turn on GitHub Pages from `main`, root folder. Confirm the demo loads at `https://suhbhandari.github.io/territory-engine/site/` and that the page finds `outputs/public/` through its relative paths. Fix the paths if it doesn't.
- About box: "Finds, ranks and briefs sales accounts from public data. Every claim is cited and checked in code. Measured where it breaks."
- Topics: `gtm-engineering`, `revops`, `lead-scoring`, `llm-evaluation`, `claude`, `sales-intelligence`.

**Checkpoint:** show the live Pages URL and the output of both history searches.

---

## P1. Load the exports into a live CRM: HubSpot (5 hours)

This closes two README limits: "Nothing has been sent or imported" and "the export files have not been loaded into a live CRM."

**Target:** a HubSpot developer test account. Use a private app token in `.env` as `HUBSPOT_TOKEN`, with these scopes: `crm.objects.companies.read`, `crm.objects.companies.write`, `crm.schemas.companies.read`, `crm.schemas.companies.write`. Add the variable to `.env.example`.

**Build:**
- **Export config:** a `hubspot` target in `export.yaml` that maps each HubSpot company property to a template over account fields, the same way the existing targets work. Property names, labels and types live in config, not in code.
- **`src/push_hubspot.py`:** generic, with no vertical terms. Two commands:
  - `make hubspot-setup` creates a property group called "Territory Engine" and every custom property in the config. It can be run again safely. `territory_engine_id` is created as a unique-value property.
  - `make push-hubspot` uses the batch upsert endpoint for companies, with `territory_engine_id` as the ID property, in batches of 100.
    - **Dry run by default.** It prints create / update / unchanged counts and writes nothing. `make push-hubspot CONFIRM=1` writes.
    - **Source.** By default it pushes the anonymized public build, so the CRM can appear in a recording without showing real names. `SOURCE=raw` pushes the private build.
    - **Rate limits.** On a 429 it retries with backoff and logs every batch to `outputs/raw/hubspot_push_log.json`.
- **Tests:** mock all HTTP; tests never touch the network. Cover:
  - the mapping
  - dry run makes no write calls
  - a second identical push creates 0 and updates 0
  - a 429 is retried, then succeeds
  - a missing token fails with a plain message

**Prove it:**
1. Run the push twice for real.
2. Record in the report card: accounts pushed, and the second run's counts (0 created, 0 changed).
3. Take one screenshot of the HubSpot company list filtered to tier A, saved as `docs/img/hubspot-tier-a.png`.
4. Update the status line in `docs/stack-fit.md` and the related README limit. Say exactly what is now proven (HubSpot test account, companies only) and what still isn't (Salesforce and Outreach imports, contacts).

**Cut line:** if the batch upsert fights back, upsert one company at a time with search-then-create. It's slower, but it ships.

**Checkpoint:** the two push outputs and the screenshot.

---

## P2. A real week-over-week refresh (1 hour, mostly waiting)

The last collection finished on 2026-10-13, so a refresh run now is about a week later. That is the weekly pair V2.md says is missing.

- Run `make refresh`, then `make triggers`.
- Add to the report card: how many accounts changed tier, how many trigger events fired, by type, and how many drafts were rewritten.
- Move "Weekly refresh" and "Trigger list" in V2.md from "what proving it needs" to what was measured. "Have a rep say whether the changes are worth acting on" stays open.

**Checkpoint:** the trigger counts.

---

## P3. Second vertical: residential home services (6 hours)

This is V2 Phase 9. It proves the claim "a new vertical is a config folder, not new code," and the result that matters is the list of core files that had to change.

**Prerequisites (timebox 2 hours together):**
- **#15:** the public build and the site read signal columns by name. Move that mapping into the vertical's config.
- **#16:** give every step a run-folder argument, `outputs/raw/<metro>-<vertical>/`, so a second run doesn't overwrite the first. *Cut line:* if #16 runs past the box, keep the single folder. Run the second vertical after copying the NYC outputs aside, and record the manual step in the write-up.

**The vertical: `config/verticals/home_services/`**
- **Accounts:** residential HVAC, plumbing and electrical contractors.
- **Seller:** a generic AI phone answering and booking product for home service businesses. Name no real company.
- **Sources:** Google Maps only. No registry.
- **Signals:** reuse the existing generic modules: website live, careers page, open roles. Hiring for dispatchers, customer service reps or technicians is the main "needs help now" signal. Add review count and number of locations if the Maps source already returns them.
- **Rubric:** in `rubric.yaml` with plain-language reasons, like the first vertical.
- **Personas:** owner or general manager, operations manager, call center manager.
- **Brief and sequence prompts** and a glossary.

**Metro:** add `config/metro/phoenix.yaml` (a large home-services market). Run on a limited sample of about 150 accounts. Print an estimate of the Google cost and get Suhaani's OK before discover runs.

**Deliverables:**
- **`docs/second-vertical.md`:** every core file that had to change and why, the time it took, and what a third vertical would still need.
- `make check-generic` passes.
- A report card for the new run: account count, tier counts, data coverage, and check pass rates.

**Cut line:** a 50-account run with briefs for tier A only.

**Checkpoint:** the core-file list and the new report card.

---

## P4. A person grades the briefs (2 hours, Suhaani, done while P1 or P3 builds)

V2.md lists "Evals with people" as not built. The existing blind grades came from a model.

- Pick the same 15 NYC briefs the model graded. Grade them by hand on the same accuracy and usefulness rubric, without looking at the model's grades first.
- Claude Code then adds `make agreement`. It computes exact agreement and within-one agreement between the hand grades and each model round, and adds the result to the report card.
- Store hand grades under `outputs/private/` (they reference real names). Publish only the agreement numbers.

---

## P5. Packaging (1.5 hours)

**README, top of the file:**
- One sentence on what it is.
- The live demo link and the Loom link.
- Three numbers: accounts found, recall against the state register, and the HubSpot push result.

**New README section, "How I built this":**
- Spec-first: Suhaani wrote the specs and the rules in CLAUDE.md.
- Built with Claude Code.
- What code checks instead of a model: citations, numbers, proper nouns, leaks, and vertical terms in core code.
- What she checked by hand.

**Loom (Suhaani records on Day 6):** follow the 90-second section of `docs/demo-script.md`, and add a 10-second clip of the HubSpot list.

---

## Definition of done

- The public repo is live, the Pages demo loads, and both history searches came back empty.
- The HubSpot push ran twice, and the second run changed nothing.
- The refresh and trigger numbers are in the report card.
- The second vertical has run and `docs/second-vertical.md` exists, or its cut line is met and stated.
- `make checks` passes.
- The README limits section matches what is now proven. Nothing is claimed that wasn't measured.

## Not in this phase

Contacts, closing the loop with outcome data, the time study, a Salesforce API write, and the V2 cleanup items (#21 to #30). They stay in V2.md.
