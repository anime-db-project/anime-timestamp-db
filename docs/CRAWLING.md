# API crawling, durable checkpoints and release integration

This is the source-aware incremental ingestion pipeline for **AniSkip** and
**Anime Skip**. It covers initial discovery, recovery, repeat checks, transparent
provenance, duplicate suppression and optional audited release imports.

## Architecture

1. Download published `anime-mapping-db/mappings.db.zst` read-only and derive
   all unambiguous MAL / AniList title identifiers. No fuzzy title matching.
2. **AniSkip**: GET `https://api.aniskip.com/v2/skip-times/{mal}/{episode}`;
   an independent per-source sliding window limits all calls/retries to **70 RPM**.
3. **Anime Skip**: authenticated POST `https://anime-skip.com/api/graphql`;
   one request can return multiple episodes and timestamp boundaries. Boundary
   intervals are calculated within the **same upstream lineage**, never between
   different third-party providers.
4. Validate, normalize and checkpoint source-native observations. A new title,
   missing title and bad upstream record get distinct persisted statuses.
5. Store the entire source state, including original normalized intervals, in
   the dedicated branches `crawler-state-aniskip` and
   `crawler-state-anime_skip`, respectively, under
   `checkpoints/<source>.json.gz`. GitHub Actions Cache is merely a
   performance fallback, and Actions Artifacts are recovery/debug outputs.
   State branches provide version history and survive cache eviction.
6. Automatically import both checkpoint snapshots into runtime and evidence
   databases when they are complete and valid. The maintainer has opted in
   to publication, subject to applicable upstream terms.

The durable state branches are **PUBLIC when this repository is public**.
Their content is source-derived data. Confirm the provider terms and
redistribution rights before starting a long-term public archive.

The crawler never puts Client IDs, tokens, account/user identifiers or
secret headers into checkpoints. Native title identifiers, episode IDs,
timestamp source IDs, timings, timestamps of checks and lineage are recorded.

## First pass: bounded, resumable bootstrap

`.github/workflows/crawl.yml` now supports:

- `mode=bootstrap`: process previously unseen candidates first, up to
  **1000 HTTP requests per source per job**. The next bounded run dispatches
  automatically when both source jobs succeed and some candidates remain.
- `remaining_runs=160` is the default **safety limit** on the number of
  automatically chained workflow runs. This is not a single 160-hour runner.
  A rate limit, fatal response, failed durable state save or job failure
  **stops chaining**; an operator can dispatch bootstrap again to resume.
- `mode=maintenance`: use the same persistent state to check newly added
  titles, due negative checks, errors after cooldown and positive checks that
  have expired. This is the default for manual and daily scheduled runs.
- Both sources run as independent workers and have their own request budgets.
  Workflow-level concurrency serializes all checkpoint writes and dispatches.
- `push` only exercises **2 requests per source**, without publishing new
  persistent checkpoints (CI smoke checks), not a full crawl.
- The daily schedule is 05:23 UTC, using the standard 1000-request budget.

**Start an initial pass** from GitHub Actions → Timestamp API crawling →
Run workflow, selecting `mode=bootstrap`, `max_requests=1000`,
`remaining_runs=160`. The workflow will dispatch subsequent batches
automatically, without manually starting 125 separate runs. Use the run
summaries to watch `initial_unchecked_after_run`; completion means zero
**known candidates**, not exhaustive coverage of every possible series in
anime history.

A bootstrap run requires the Anime Skip Client ID. Without it, preflight now
fails immediately rather than silently omitting the source.

At the currently indexed volume (~124k AniSkip episode candidates and ~22k
Anime Skip titles), a complete initial pass needs on the order of **125
batches**, and at 70 RPM requires **at least ~30 hours** of combined crawl
time plus workflow overhead. It can take longer with retries or slower APIs.
An actual source rate limit (HTTP 403/429) stops the affected source safely
rather than bypassing the provider.

### A crucial episode-discovery limitation

The mapping DB maps **titles**, not canonical episode counts. For AniSkip,
existing MAL-native episodes in released `timestamps.db` seed the episode
list, including gaps and two speculative future episodes, bounded by
`--max-episodes` (default 96 unless independently known). When no episode
hints exist, episodes 1-2 are checked. **A positive API result now advances
the discovery frontier** on subsequent runs.

However, titles with no results in the initial probes may still contain
unseen later episodes. A completed bootstrap therefore means all *known*
candidates were checked, not that the API definitively contains no additional
episodes. Separate episode-count discovery is a future enhancement.

## Incremental refresh and failure handling

| State | Persisted result | Earliest normal retry |
| --- | --- | --- |
| Found data | `found` and all segment observations | 30 days |
| No data | `missing` | 14 days |
| Broken Anime Skip internal timestamp row | `source_error`, or preserve previously found data, with a diagnostic | 14 days |
| 403 / 429 | Stop the source, preserve collected state | Subsequent operator/schedule run |
| Network/5xx failures | Limited retries within the same request budget; abort if exhausted | Subsequent run |

The current crawler puts new/unseen keys ahead of due rechecks. It writes
checkpoint files atomically every 25 completed candidates and on exit,
and records each outbound request, including retries, against the RPM
and total request budgets.

GitHub API checkpoint persistence verifies the bytes written. If a known
durable state branch exists but its file is absent or invalid, the workflow
**fails rather than silently resetting** accumulated work. An initial run
may seed its state from the existing GitHub Actions cache, to preserve data
collected before the durable-store upgrade.

## Source-native boundaries and provenance

- `aniskip`: native MAL episode, `aniskip` consensus lineage. The CSV source
  and API share the lineage to avoid duplicate independent votes.
- `anime_skip`: native AniList title ID, upstream episode UUID, season,
  absolute number and original lineage (e.g. `ANIME_SKIP`,
  `BETTER_VRV`, `ANISKIP`). Third-party mirrors use the
  **underlying** lineage rather than an artificial extra Anime Skip vote.
- An AniList episode number is **not** automatically considered equivalent to
  MAL episode `ep:N`. Native Anime Skip episodes are first checked against the
  independently built `episode_ids` index (which is now populated **before**
  the API stage). Where that is missing, an exact, uniquely invertible
  AniBridge `AniDB:R -> AniList episode + MAL episode` mapping may prove the
  playback-unit identity. All three native title IDs must resolve to the **same
  AMDB anchor**. This can create a new canonical episode or title without
  assuming AniList and MAL episode numbers are equal.
- The AniBridge route is rejected for split/combined ratio mappings, absent or
  conflicting MAL targets, ambiguous inverse ranges, multiple upstream
  episode UUIDs for a purported native episode number, and Anime Skip
  season-local episodes without a proven absolute/first-season identity.
  Disputed observations remain queryable in `source_segments`.
  Accepted bridge observations are tagged `exact-anibridge-api`; their exact
  AniDB, MAL and AniList evidence is included in the record metadata.
- Unknown upstream lineages are preserved but are **consensus-ineligible**.
- The catalog excludes a provider ID shared by multiple AMDB anchors; export
  rejects mismatched checkpoint episode keys and non-positive source records.
  Neither case may silently attribute observations to the wrong anime.
- The release importer resolves the latest provider IDs to AMDB anchors again,
  validates every segment, prevents duplicate source IDs and records
  normalization decisions in `timestamps-evidence.db`.
- Source snapshot hashes, import counts and exact distribution notices are
  included in `manifest.json`. Changes are included in release fingerprint
  comparisons, so unchanged snapshots do not alone trigger new releases.

## Release integration: automatic once both sources are ready

The maintainer has enabled automatic API-data imports in both Database build
and Release workflows. The workflows check and validate the source-specific
checkpoints. When **both** exist, they are compiled into the SQLite databases.
If neither or only one source checkpoint exists, the workflow records which
sources are pending and builds from the other datasets without API imports.
Corrupted existing checkpoints are fatal instead of silently discarded.

No `ENABLE_API_CRAWL_IMPORT` Actions variable is required. The builder still
requires the explicit redistribution flag, supplied automatically only once
both checkpoints are validated:

```sh
anime-timestamp-db build --output-dir artifacts \
  --api-checkpoint-dir api-checkpoints \
  --allow-api-redistribution
```

Both API sources are visible separately as `aniskip-api` and
`anime-skip-api`, with `ANIME_SKIP_API_NOTICE.md` in the release.
Source-native unresolved Anime Skip episodes remain available by their
source-specific references. The compiler fails closed if an explicitly
requested checkpoint is missing; it cannot silently publish partial data.

The following remain distinct:

- `crawler-state-*` branches: durable checkpoint and recovery history;
- short-lived Actions artifacts: audit/debugging and offline exports;
- `timestamps.db` and `timestamps-evidence.db`: automatic all-source API
  import after both durable checkpoints are ready; no partial imports.

## CLI and offline verification

```sh
# Run a bounded local crawl:
python scripts/crawl_timestamps.py --source aniskip \
  --mapping-db mappings.db --timestamps-db timestamps.db \
  --max-requests 1000 --rpm 70

ANIME_SKIP_CLIENT_ID='<private-client-id>' \
python scripts/crawl_timestamps.py --source anime_skip \
  --mapping-db mappings.db --max-requests 1000 --rpm 70

# Offline export only: no API access, no Client ID required:
python scripts/crawl_timestamps.py --source anime_skip \
  --mapping-db mappings.db --export-only

# GitHub Actions alone may restore/persist authenticated durable state:
python scripts/checkpoint_store.py restore --source aniskip
python scripts/checkpoint_store.py persist --source aniskip
```

Do not add Client IDs or authentication headers to code, logs, commits or
release assets. The GitHub Actions secret remains
`ANIME_SKIP_CLIENT_ID`.

Important: Running `mode=bootstrap` is an intentional potentially
multi-day continuous API load. Use it only when the providers' API usage
policy permits the collection volume and the public archive is authorized.
