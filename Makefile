.PHONY: discover backfill enrich enrich-sample score brief brief-sample sequence sequence-sample export public site check-generic test leak-test checks snapshot fresh triggers refresh stability recall hubspot-setup push-hubspot agreement

# Defaults come from config/defaults.yaml. Override for one run, for example:
#   make score VERTICAL=<name> METRO=config/metro/<name>.yaml
VERTICAL ?=
METRO ?=
# A named run keeps its files in outputs/raw/<RUN>/ and outputs/public/<RUN>/ (src/paths.py),
# so a second metro or vertical does not overwrite the first. Unset: the shipped run.
#   make discover RUN=<metro>-<vertical> VERTICAL=<name> METRO=config/metro/<name>.yaml
RUN ?=
export TE_RUN = $(RUN)
V = $(if $(VERTICAL),--vertical $(VERTICAL))
M = $(if $(METRO),--metro $(METRO))

discover:
	python3 src/discover.py $(M) $(V)

backfill:
	python3 src/backfill.py $(V)

enrich:
	python3 src/enrich.py $(V)

enrich-sample:
	python3 src/enrich.py $(V) --limit 10

score:
	python3 src/score.py $(M) $(V)

brief:
	python3 src/brief.py $(V)

brief-sample:
	python3 src/brief.py $(V) --limit 5

sequence:
	python3 src/sequence.py $(V)

sequence-sample:
	python3 src/sequence.py $(V) --limit 5

export:
	python3 src/export.py $(V)

# HubSpot companies through the API (needs HUBSPOT_TOKEN in .env). Setup creates the
# property group and custom properties; safe to run again. Push is a dry run unless
# CONFIRM=1, and sends the anonymized public build unless SOURCE=raw.
SOURCE ?= public
hubspot-setup:
	python3 src/push_hubspot.py setup $(V)

push-hubspot:
	python3 src/push_hubspot.py push $(V) --source $(SOURCE) $(if $(CONFIRM),--confirm)

public:
	python3 src/anonymize.py $(M) $(V)
	python3 src/evals.py $(V)

# Serves the whole project folder, because site/index.html reads the published data from
# outputs/public/. Binds to 127.0.0.1 explicitly: the default binds to IPv6 only, which some
# machines cannot reach as localhost. Opens the page itself so a live demo is one command.
site: public
	@echo "Open http://localhost:8000/site/ (Ctrl-C to stop)"
	@(sleep 1 && python3 -c "import webbrowser; webbrowser.open('http://localhost:8000/site/')" >/dev/null 2>&1) &
	python3 -m http.server 8000 --bind 127.0.0.1

check-generic:
	python3 scripts/check_generic.py

test:
	python3 -m pytest -q tests

leak-test:
	python3 scripts/leak_test.py

# The three checks to run before calling any change done.
checks: check-generic test leak-test

# Keep a copy of the current run's private data in outputs/raw/runs/<date>/.
snapshot:
	python3 scripts/snapshot.py

# A fresh run: keep a copy of the current run, then rebuild the account list and re-check
# every signal. Paid Google calls in discover and for any new account in backfill.
fresh:
	python3 scripts/snapshot.py --fresh-signals
	$(MAKE) discover backfill enrich score export

# How much of the ranking survives a change to the rubric's weights. Reads the scored
# file only; calls nothing and costs nothing.
stability:
	python3 scripts/tier_stability.py $(V)

# How much of the territory the list actually found, against a public register that is
# meant to be complete for it. Downloads the register, so it needs network access.
recall:
	python3 scripts/recall_check.py $(V)

# A person's grades of the briefs against each model grading round: exact and within-one
# agreement. Reads outputs/private/ (real names); writes numbers only, then rebuilds the report card.
agreement:
	python3 scripts/agreement.py
	python3 src/evals.py $(V)

# What changed since the last snapshot: outputs/raw/triggers.csv (private).
triggers:
	python3 src/triggers.py $(V)

# The weekly refresh: keep a copy of this run, re-check every signal, re-score, list what
# changed, rewrite only the briefs and sequences whose facts changed, rebuild, check.
# Paid model calls for the rewritten drafts. Run discover (make fresh) monthly instead.
refresh:
	python3 scripts/snapshot.py --fresh-signals
	$(MAKE) enrich score triggers brief sequence export public checks
