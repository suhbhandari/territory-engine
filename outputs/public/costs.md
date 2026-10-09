# Costs

Generated 2026-10-09. Model costs are measured from the token usage logged for each brief and sequence in the current run, priced at the per-token rates set in the vertical's config. They cover one clean pass; samples, retries and regenerated drafts during development cost extra.

| Step | Model | Items | Avg input tokens | Avg output tokens | Cost per item | Total |
|---|---|---|---|---|---|---|
| Briefs | claude-opus-5-5 | 276 | 1974 | 600 | $0.0199 | $5.50 |
| Sequences | claude-opus-5-5 | 276 | 2115 | 504 | $0.0185 | $5.12 |
| **Model total** | | | | | | **$10.62** |

## Other costs

These are not logged by the pipeline. They are estimates from request counts and list prices.

| Item | Requests | Estimated cost | Basis |
|---|---|---|---|
| Google Places discovery searches | up to 45 per run | about $1.50 | Text Search with website and phone fields, list price about $35 per 1,000 requests |
| Google Places website lookups (one-time backfill, cached) | 1,238 | about $43 | Same price tier; before any free monthly allowance; not confirmed against a billing statement |
| Provider registry and agency websites | several thousand | $0 | Free public sources, no key |

Scoring, export, anonymization and this report make no paid calls.
