# External skip-timestamp provider acknowledgements

These are third-party services. The anime-db-project is **not** sponsored by,
affiliated with or officially endorsed by any of them. Acknowledging a provider
does not create permission to bulk-download, redistribute or mirror its data.

| Provider | Official website | Data/permission status |
| --- | --- | --- |
| IntroDB | https://introdb.app/ | Public single-episode reads; bulk extraction and competing databases require express permission; see https://introdb.app/docs/terms |
| PublicMetaDB | https://publicmetadb.com/ | Bearer-key read access. Obtain the key and confirm permitted bulk/redistribution scope. |
| TheIntroDB | https://theintrodb.org/ | Public API v4 read access; 30 requests per 10 seconds observed. Bulk publishing terms need separate verification. |
| IntroHater | https://introhater.com/ | Public per-episode read endpoint, but https://introhater.com/terms.html prohibits automated scraping without permission. |

Thanks to the communities and contributors who maintain these services.

**Data provenance**: IntroHater aggregates some AniSkip, Anime Skip and
IntroDB records. Its re-hosted records must never be counted as independent
evidence. Third-party episodes with TVDB/IMDb/TMDB season+episode coordinates
remain source-only until independently matched to an AMDB anime episode.

**Operational policy**: A provider may be configured and tested against
mock responses without collecting its dataset. The crawler's automatic bulk
workflow is disabled for providers requiring upstream permission, and SQLite
republication requires explicit source selection plus a separate permission
confirmation. No API token is stored in public checkpoints.

The request limits in `config/crawler_sources.json` are conservative client-side
caps, not permission to bulk extract. Unknown upstream limits use a maximum
of 2,000 requests per run and lower pacing, not a guessed provider guarantee.
