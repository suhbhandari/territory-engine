.PHONY: discover backfill enrich enrich-sample score brief brief-sample sequence sequence-sample check-generic

discover:
	python3 src/discover.py

backfill:
	python3 src/backfill.py

enrich:
	python3 src/enrich.py

enrich-sample:
	python3 src/enrich.py --limit 10

score:
	python3 src/score.py

brief:
	python3 src/brief.py

brief-sample:
	python3 src/brief.py --limit 5

sequence:
	python3 src/sequence.py

sequence-sample:
	python3 src/sequence.py --limit 5

check-generic:
	python3 scripts/check_generic.py
