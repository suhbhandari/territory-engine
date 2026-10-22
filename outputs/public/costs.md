# Costs

Generated 2026-10-22. Model costs are measured from the token usage logged for each brief and sequence in the current run, priced at the per-token rates set in the vertical's config. They cover one clean pass; samples, retries and regenerated drafts during development cost extra.

| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |
|---|---|---|---|---|---|---|
| Briefs | claude-opus-5-5 | 292 | 2498 | 1209 | $0.0342 | $9.98 |
| Sequences | claude-opus-5-5 | 295 | 2503 | 525 | $0.0205 | $6.05 |
| **Model total** | | | | | | **$16.03** |

The items logged include 49 briefs and 52 sequences that are not current (groups that have since left tiers A and B, or text held back as out of date); they were paid for. A draft that was rewritten replaces its earlier row, so the cost of the earlier version is not in these totals.

## Other costs (estimates written by hand)

These are not logged by the pipeline. They are estimates from request counts and list prices, typed into the vertical's evals.yaml.

| Item | Requests | Estimated cost | Basis |
|---|---|---|---|
| Google Places discovery searches | up to 45 per run | about $1.50 | Text Search with website and phone fields, list price about $35 per 1,000 requests |
| Google Places website lookups (one-time backfill, cached) | 1,252 | about $44 | Same price tier; before any free monthly allowance; not confirmed against a billing statement |
| Provider registry and agency websites | several thousand | $0 | Free public sources, no key |

Scoring, export, anonymization and this report make no paid calls.
