# Optional third-party timestamp sources

The adapters are available for **IntroDB**, **PublicMetaDB**, **TheIntroDB** and
**IntroHater**, in addition to the existing AniSkip and Anime Skip crawlers.
They do not imply bulk access or data redistribution permission.

## Acknowledgment

These are valuable independent community projects, and are linked by name in
the README and `EXTERNAL_SOURCES_NOTICE.md`. Neither their maintainers nor
anime-db-project are represented as sponsors/official contributors of the
other project without a verified relationship. Providing a link, attribution
or “sponsor” label does not override provider terms.

- IntroDB: https://introdb.app/
- PublicMetaDB: https://publicmetadb.com/
- TheIntroDB: https://theintrodb.org/
- IntroHater: https://introhater.com/

## Request policies

Edit `config/crawler_sources.json` to tune **each provider independently**:

- `max_requests`: hard per-run HTTP budget, including retry calls;
- `per_second`, `per_minute`, `per_hour`: independent sliding windows;
- `delay_seconds: [min, max]`: small randomized **load-smoothing interval**
  between calls; not a method for evading bot protections;
- `retry_429_wait_seconds`: fallback wait if Retry-After is absent;
- `max_429_wait_seconds`: ceiling for in-job waiting; longer provider
  cooldowns end the run immediately with a saved checkpoint;
- `requires_bulk_permission`: provider-specific explicit approval gate.

TheIntroDB documented anonymous rate is 30 per 10 seconds plus usage limits,
including a separate quota for repeatedly requesting the same media.
The configured pace of 2/s is below this. IntroHater's public endpoint has
a configured server-wide limit of 5,000/hour; this crawler uses 3,000/hour,
*but is disabled for automatic bulk scraping absent permission*. The
remaining profiles have conservative locally imposed limits, not verified
upstream throughput guarantees. **2,000** is the default per-run cap when
no lower provider run quota was verified. Never probe by hammering an API
until it starts returning 429.

On a 429, the requester respects Retry-After or a supported rate reset
header, waits once (if within the configured cap and budget), then retries
once. A second 429 ends the job gracefully, marks `stopped_reason`, saves
the partial JSONL and durable source checkpoint, and disables immediate
bootstrap chaining. A 403 is an access failure and is never retried.

## HTTP client identity and Cloudflare access

All six crawlers send a consistent, project-identifying HTTP
`User-Agent: anime-timestamp-db/0.3 (+https://github.com/anime-db-project/anime-timestamp-db)`
and `Accept: application/json`. To set your own truthful, identifying
User-Agent, configure the optional GitHub Actions repository **variable**
`TIMESTAMP_CRAWLER_USER_AGENT` or use `--user-agent` in the CLI.
PublicMetaDB credentials remain in the `PUBLICMETADB_API_KEY` Actions **secret**.

Changing User-Agent **does not bypass Cloudflare Managed Challenges**.
On a 403 HTML challenge, the crawler stops without trying CAPTCHA solvers
or browser impersonation. Request an approved machine-to-machine API
integration or an authorized WAF exception from the provider. Send the
`cf_ray` value printed in the report; do not send the API key.

## Authorization and automated workflows

GitHub Actions uses the **same** `config/crawler_sources.json` as the
crawler. Set `requires_bulk_permission: false` only after confirming that
the project operator has the right to collect the selected provider's data.
The old, separate `*_BULK_APPROVED` repository variables are no longer
consulted: they previously caused the whole source to be silently skipped
even when the config explicitly enabled crawling.

| Source | Required setup |
| --- | --- |
| TheIntroDB | Operator permission confirmed in source config |
| PublicMetaDB | Operator permission confirmed in source config and Actions secret `PUBLICMETADB_API_KEY` |
| IntroDB | Operator permission confirmed in source config (see upstream terms) |
| IntroHater | Operator permission confirmed in source config (see upstream terms) |

If PublicMetaDB is enabled but its API key is missing, preflight fails
**visibly** instead of reporting a misleading successful crawl. Other
providers marked as requiring permission emit an explicit warning and are
skipped. GitHub Actions never prints API keys in reports or checkpoints.

Push, scheduled and manually dispatched runs now use the source's normal
per-run request quota by default (2,000 unless overridden) and persist their
checkpoints; `--max-requests` can lower the budget on a manual run. The
two existing AniSkip/Anime Skip sources retain the same bounded pacing.

A small read-only test can be run with `--only-anchor` and
`--max-requests 1`, subject to API terms. Test parsers and rate
handling without any network traffic with `python -m unittest`.

To crawl after the necessary permission:

```bash
python -m scripts.crawl_timestamps \
  --source theintrodb \
  --mapping-db inputs/mappings.db \
  --max-requests 100 \
  --state-dir .build-cache/crawler-state \
  --output-dir crawler-output
```

Release builds **never silently ingest the new providers**, even if their
checkpoint branches are present. The existing automatic AniSkip/Anime Skip
release import is unchanged. For separately permitted external data, the
operator must select each source:

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --external-checkpoint-dir external-checkpoints \
  --external-source theintrodb \
  --allow-external-data-redistribution
```

A selected source must have `external-checkpoints/<source>.json.gz`. Its
provided title IDs are independently revalidated with the pinned AMDB
release and stored via `source_title_refs`. Because IMDb/TVDB/TMDB
series+season+episode does **not** generally equal a MAL/AniList episode,
all new ranges initially remain in `source_segments`. No new canonical
episode or independent consensus vote is invented, and copied IntroHater
lineages are labeled with their original upstream origin.

## API formats

- IntroDB: IMDb TV ID + season + episode; `intro`, `recap`, `outro`,
  `post_credits`, possible explicit absence flags.
- PublicMetaDB: TMDB TV ID + media_type=tv + season + episode; Bearer authorization;
  explicit bounded `*_start_ms`/`*_end_ms` intervals only.
- TheIntroDB API **v4**: TVDB ID (fallback IMDb/TMDB TV), season + episode;
  arrays of `intro`, `recap`, `credits`, `preview`; some ends may
  be null and must **not** be guessed.
- IntroHater: IMDb + source season + episode; source field and contributor
  lineage retained; a public read endpoint does not mean bulk permission.

See `EXTERNAL_SOURCES_NOTICE.md` for third-party attribution and restrictions.
