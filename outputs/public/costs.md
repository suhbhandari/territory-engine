# Costs

Generated 2026-10-12. Model costs are measured from the token usage logged for each brief and sequence in the current run, priced at the per-token rates set in the vertical's config. They cover one clean pass; samples, retries and regenerated drafts during development cost extra.

| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |
|---|---|---|---|---|---|---|
| Briefs | claude-opus-5-5 | 264 | 1973 | 597 | $0.0198 | $5.24 |
| Sequences | claude-opus-5-5 | 264 | 2114 | 503 | $0.0185 | $4.89 |
| **Model total** | | | | | | **$10.13** |

## Other costs

These are not logged by the pipeline. They are estimates from request counts and list prices.

| Item | Requests | Estimated cost | Basis |
|---|---|---|---|
| Google Places discovery searches | up to 45 per run | about $1.50 | Text Search with website and phone fields, list price about $35 per 1,000 requests |
| Google Places website lookups (one-time backfill, cached) | 1,238 | about $43 | Same price tier; before any free monthly allowance; not confirmed against a billing statement |
| Provider registry and agency websites | several thousand | $0 | Free public sources, no key |

Scoring, export, anonymization and this report make no paid calls.
