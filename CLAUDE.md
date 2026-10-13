# CLAUDE.md

## Generalization rule

The core engine (discovery, backfill, enrichment, scoring, weight-sensitivity, briefs, sequences, evals, anonymization, exports, triggers, site) must contain no vertical-specific logic. Everything vertical-specific lives in `config/verticals/<name>/`: discovery source configs, signal configs, rubric.yaml, personas.yaml, brief prompt, and a glossary. Signals and discovery sources implement a small shared interface (`fetch(params, geo) → DataFrame`).

v1 ships one vertical: `home_care_post_acute`.

**Any vertical-specific term, source, signal, or prompt text found in core code is a bug. Move it to `config/verticals/` before the checkpoint.**

The `make check-generic` target enforces this. It runs before every checkpoint. A passing check is a prerequisite for phase completion.

## Directory layout

```
config/
  metro/              ← geo only: state, zip_prefixes, search_cities
  verticals/<name>/   ← everything vertical-specific
src/
  sources/            ← generic source modules implementing fetch(params, geo)
  discover.py         ← generic orchestrator
  score.py            ← generic scorer
  brief.py            ← generic brief generator
  ...
outputs/
  raw/                ← discovery output, not committed
  public/             ← anonymized, committed
docs/                 ← GTM packaging docs
scripts/              ← check-generic and other dev tools
```

## Phase checkpoints

Before marking any phase complete:
1. `make check-generic` passes with PASS
2. Definition of done for that phase is fully met (not partially met)
3. No features from future phases have been introduced

If a request looks like polish on a completed phase rather than progress on the current phase, name it and hold.
