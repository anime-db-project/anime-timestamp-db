# Live Anime Skip and AniSkip API observations

The opt-in API importer in Anime Timestamp DB consumes two independently
collected, source-attributed API checkpoints. These are **not** the same as
AniSkip's independently published sanitized CSV dump.

- **AniSkip API:** https://api.aniskip.com/api-docs
- **Anime Skip API:** https://anime-skip.com/ and https://github.com/anime-skip/public-api

Anime Skip publishes its API server code under GPL-3.0. That **does not**
automatically grant a GPL-3.0 license to crowd-contributed timing data or
rehosted third-party timestamps. The API homepage advertises free application
access, not necessarily unrestricted bulk redistribution. AniSkip's sanitized
public CSV release likewise does not independently license all live API data.

The operator must independently verify applicable data licensing, attribution
and bulk redistribution permission **for each upstream** before enabling
release imports with `--api-checkpoint-dir` and
`--allow-api-redistribution`. No upstream dataset is labelled ODbL, MIT,
Apache or GPL solely from the upstream software license.

### Preservation and normalization

Every imported record carries its exact checkpoint hash, native source title
and episode identifier, timestamp type/range, upstream lineage, and original
API source. Original user/account identifiers and private API Client IDs are
never included. Unresolved AniList episodes stay queryable via source-only
rows rather than being silently assigned MAL episode numbers.

When an API mirrors another upstream, its lineage is mapped to that
underlying provider, so shared data does not produce independent consensus
votes. Unrecognized upstream lineages cannot vote in consensus.

These notices must accompany any release that includes API-derived rows.
