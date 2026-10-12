.PHONY: discover backfill enrich enrich-sample score brief brief-sample sequence sequence-sample export public site check-generic test leak-test checks snapshot fresh

# Defaults come from config/defaults.yaml. Override for one run, for example:
#   make score VERTICAL=<name> METRO=config/metro/<name>.yaml
VERTICAL ?=
METRO ?=
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

public:
	python3 src/anonymize.py $(M) $(V)
	python3 src/evals.py $(V)

site: public
	@echo "Open http://localhost:8000/site/ (Ctrl-C to stop)"
	python3 -m http.server 8000

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
