.PHONY: discover backfill enrich enrich-sample score brief brief-sample sequence sequence-sample export public site check-generic

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
	python3 src/score.py $(V)

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
