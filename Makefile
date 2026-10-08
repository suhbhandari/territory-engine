.PHONY: discover backfill enrich check-generic

discover:
	python3 src/discover.py

backfill:
	python3 src/backfill.py

enrich:
	python3 src/enrich.py

enrich-sample:
	python3 src/enrich.py --limit 10

check-generic:
	python3 scripts/check_generic.py
