# Costs

Generated 2026-10-13. Model costs are measured from the token usage logged for each brief and sequence in the current run, priced at the per-token rates set in the vertical's config. They cover one clean pass; samples, retries and regenerated drafts during development cost extra.

| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |
|---|---|---|---|---|---|---|
| Briefs | claude-opus-5-5 | 289 | 2135 | 1174 | $0.0320 | $9.26 |
| Sequences | claude-opus-5-5 | 292 | 2251 | 513 | $0.0193 | $5.63 |
| **Model total** | | | | | | **$14.89** |

The items logged include 45 briefs and 48 sequences that are not current (groups that have since left tiers A and B, or text held back as out of date); they were paid for. A draft that was rewritten replaces its earlier row, so the cost of the earlier version is not in these totals.

## Other costs (estimates written by hand)

These are not logged by the pipeline. They are estimates from request counts and list prices, typed into the vertical's evals.yaml.

| Item | Requests | Estimated cost | Basis |
|---|---|---|---|
| Google Places discovery searches | up to 45 per run | about $1.50 | Text Search with website and phone fields, list price about $35 per 1,000 requests |
| Google Places website lookups (one-time backfill, cached) | 1,252 | about $44 | Same price tier; before any free monthly allowance; not confirmed against a billing statement |
| Provider registry and agency websites | several thousand | $0 | Free public sources, no key |

Scoring, export, anonymization and this report make no paid calls.
