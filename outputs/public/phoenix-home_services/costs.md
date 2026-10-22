# Costs

Generated 2026-10-22. Model costs are measured from the token usage logged for each brief and sequence in the current run, priced at the per-token rates set in the vertical's config. They cover one clean pass; samples, retries and regenerated drafts during development cost extra.

| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |
|---|---|---|---|---|---|---|
| Briefs | claude-opus-5-5 | 15 | 2406 | 1132 | $0.0323 | $0.48 |
| Sequences | claude-opus-5-5 | 15 | 2220 | 726 | $0.0234 | $0.35 |
| **Model total** | | | | | | **$0.83** |

The items logged include 0 briefs and 0 sequences that are not current (groups that have since left tiers A and B, or text held back as out of date); they were paid for. A draft that was rewritten replaces its earlier row, so the cost of the earlier version is not in these totals.

## Other costs (estimates written by hand)

These are not logged by the pipeline. They are estimates from request counts and list prices, typed into the vertical's evals.yaml.

| Item | Requests | Estimated cost | Basis |
|---|---|---|---|
| Google Places discovery searches | up to 9 per run (3 searches x 3 pages, 1 city) | about $0.35 | Text Search with website and phone fields, list price about $35 per 1,000 requests, before any free monthly allowance |
| Contractor websites | about 150 | $0 | Free, no key |

Scoring, export, anonymization and this report make no paid calls.
