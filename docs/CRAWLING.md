# Incremental API crawlers (AniSkip and Anime Skip)

This is the **first, collection-only stage** of API crawling. It does not modify
published `timestamps.db`, `timestamps-evidence.db`, `mappings.db`, or automatic
GitHub Releases. The output is an intermediate snapshot for validation, not an
automatically redistributed dataset.

## Sources and identity

| Source | Method | Identity | One request returns | Max RPM |
| --- | --- | --- | --- | --- |
| AniSkip | `GET https://api.aniskip.com/v2/skip-times/{mal}/{episode}` | Confirmed MAL ID from `mappings.db` | Skip intervals for an episode | **70** |
| Anime Skip | `POST https://anime-skip.com/api/graphql` | Confirmed AniList ID from `mappings.db` | All known episodes and their boundary timestamps for a show | **70** |

Both source jobs run independently and can execute concurrently. **Each
source has one request worker**, and all of its HTTP calls (including retries)
pass through a sliding one-minute limiter. A GitHub Actions concurrency group
prevents concurrent executions of the entire crawler workflow.

The crawl is driven by **all unambiguous MAL/AniList identities from the
published `anime-mapping-db`**. It never excludes an entire title because a
timestamp from another source already exists. AniSkip episode candidates are
derived from confirmed MAL episode keys in the existing `timestamps.db`; for
titles with no known episode numbers, the default discovery probe is episodes
1 and 2. For already known episodes, it also probes gaps and two prospective
episodes (bounded by `--max-episodes`). This is deliberately **not** an
authoritative episode-count discovery service: unseen episode 30 cannot be
found from `mappings.db` alone.

Anime Skip's points are **boundaries**, not ranges. We construct an interval
using the next boundary from the **same upstream timestamp source**, or the
known episode duration. The raw `upstream_lineage` field remains in the
snapshot; third-party mirrored observations must not count as additional
independent votes merely because the response came through Anime Skip.

## State is outside the databases

Files in `.build-cache/crawler-state/`:

- `aniskip.json.gz` — previous responses, including negative results and
  timestamps of checks by MAL title + episode
- `anime_skip.json.gz` — previous response observations by AniList title

Files in `crawler-output/`:

- `<source>.jsonl.gz` — normalized candidate observations; each row includes
  source identity, stable `anchor_id`, episode, exact intervals, upstream
  lineage, and segment ID
- `<source>-report.json` — request counts, mapping SHA, errors, and coverage

These are **not published SQLite tables**. API credentials are not written to
checkpoints or output files. Checkpoints are written atomically, every 25
completed requests and at exit, and restored by the dedicated Actions cache.
The workflow also uploads recovery copies as short-lived Actions artifacts.
Caches and artifacts are **not permanent storage**; if they expire, crawling
may have to start over. A durable storage policy will be needed before
long-running exhaustive crawling.

Success and negative results are rechecked after 30 and 14 days respectively.
Errors/HTTP 403/429 terminate that source's run without deleting prior state.
Requests are budgeted (`--max-requests`) and retries consume the same budget.

## GitHub Actions

Workflow: [`crawl.yml`](../.github/workflows/crawl.yml)

- Automatic bounded daily crawl at **05:23 UTC**
- Manual trigger using `workflow_dispatch`
- On crawler-code pushes only: **2 requests/source** for a small smoke test
- Routine budget: **500 requests/source/run**
- Hard manual budget: 1–5000 requests/source
- `70 RPM` on both AniSkip and Anime Skip, with API 429/403 stop behavior
- Max job runtime: 90 minutes; all outputs are separate Actions artifacts

For Anime Skip, configure an Actions repository secret named
**`ANIME_SKIP_CLIENT_ID`** under **Settings → Secrets and variables → Actions**.
The crawler **does not** hardcode or upload the ID found on any server.
Without this secret, only the Anime Skip job is cleanly skipped; AniSkip runs.

## Local usage

Install the project:

```bash
python -m pip install -e .
```

Prepare the reference databases from current mapping and timestamp Releases
(`mappings.db` and optionally `timestamps.db`). The workflow downloads
these references automatically.

```bash
python scripts/crawl_timestamps.py \
  --source aniskip --mapping-db mappings.db \
  --timestamps-db timestamps.db --rpm 70 --max-requests 500

ANIME_SKIP_CLIENT_ID='your-private-id' python scripts/crawl_timestamps.py \
  --source anime_skip --mapping-db mappings.db \
  --rpm 70 --max-requests 500

python scripts/crawl_timestamps.py \
  --source anime_skip --mapping-db mappings.db --dry-run
```

The results are stored under `crawler-output/`; the checkpoint defaults to
`.build-cache/crawler-state/`.

## Publication gate

The existing builder continues to use the proven public snapshot imports.
The new crawler's API observations **are not silently included in releases**:
we first need tests of episode normalization and cross-source provenance,
snapshot durability, and clarification of bulk redistribution terms from each
provider. AniSkip's publicly exported CSV and its live API are not equivalent
licensing guarantees. This design keeps the current published databases safe
while letting the crawler gather evidence for a future importer.
