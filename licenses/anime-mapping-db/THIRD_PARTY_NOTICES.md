# Third-party data notices

Anime Mapping DB is compiled from independent public datasets. This file records the sources and licensing notes used by the builder; it is not a substitute for reading each upstream project's current license and terms.

For the project-wide distinction between Apache-2.0 source code and generated database artifacts, also see [`DATA_LICENSE.md`](DATA_LICENSE.md).

| Source | Role | Licensing / attribution note |
| --- | --- | --- |
| Fribb/anime-lists | Required direct | No explicit dataset license is declared by the builder; review the upstream repository before redistribution. |
| Kometa-Team/Anime-IDs | Required direct | Repository is MIT; generated data contains mappings derived from upstream projects and may carry additional obligations. |
| Anime-Lists/anime-lists | Required direct | No explicit dataset license is declared by the builder; review upstream terms before redistribution. |
| cplieger/animap | Required direct | Dataset is ODbL 1.0 + DbCL 1.0; project code is Apache-2.0. |
| cedya77/anime-offline-database | Optional direct | Compiled database is ODbL 1.0 + DbCL 1.0. This maintained fork replaces the old manami-project download in the builder while retaining the `manami` evidence lineage. |
| anibridge/anibridge-mappings | Optional direct | Repository is MIT; generated mappings may inherit obligations from upstream datasets. |
| Wikidata | Optional direct + supplemental | Wikidata structured data is CC0 1.0. QLever is the primary bulk SPARQL backend with WDQS fallback; both query the same Wikidata lineage. Bahamut retains a bundled CC0 bootstrap snapshot for first-build endpoint outages. |
| rensetsu/db.notify.rensetsu-mirai | Optional direct | Repository is MIT. Builder consumes the public GitHub JSON dump, not Notify or another external API. |
| kawaiioverflow/arm | Optional direct | Package metadata declares MIT. Builder consumes `arm.json` from GitHub. |
| rensetsu/db.trakt.extended-anitrakt | Optional direct | Repository is MIT (archived but public). TV and movie JSON dumps are separate dataset inputs; season IDs are intentionally excluded. |
| rensetsu/db.rensetsu.public-dump / SilverYasha | Optional direct | Repository is CC0-1.0. Builder consumes the public SilverYasha JSON dump and does not scrape the site. |
| rensetsu/db.rensetsu.public-dump / AnimeThemes | Supplemental | Repository is CC0-1.0. Builder consumes the converted AnimeThemes GitHub dump and does not call AnimeThemes APIs. |
| anime-and-manga/lists | Optional corroborating | Public GitHub mapping dump with no explicit dataset license in the repository; review upstream terms before redistribution. Its weight is below the single-source acceptance threshold. |
| shinkro/community-mapping | Optional corroborating | Repository is MIT. Only title-level MAL↔TVDB-series and MAL↔TMDB-movie mappings are imported; season/episode routing and generated AniDB fields are excluded. |
| notseteve/AnimeAggregations | Supplemental | Repository uses the Unlicense, but the aggregate contains external/upstream identifiers. It is used only after two trusted anchors agree, and generic/adaptation resources are excluded. |
| Wikidata multi-ID | Supplemental | Same CC0 Wikidata lineage as above. Adds only anchor-validated missing IDs/QIDs; QLever and WDQS are query backends, not separate evidence sources. |
| nattadasu/animeApi | Supplemental | Compiled database is ODbL 1.0 + DbCL 1.0; software code is MIT. Builder consumes only the GitHub-hosted `v3/database/animeapi.tsv`, never AnimeAPI's REST service. |

## Supplemental lineage policy

AnimeAPI and AnimeAggregations contain data that can overlap with direct sources already used by Anime Mapping DB. Wikidata multi-ID is intentionally conservative because one Wikidata item can still represent a franchise/season concept differently from another catalogue. These sources therefore run only after the direct-source graph has been finalized once.

A supplemental item must contain at least two exact base IDs that are already connected by an accepted direct edge with no directional conflict. Only then may missing targets be attached. Ambiguous multiple IDs for the same target provider are skipped. AnimeAPI also excludes season-only fields and rows marked potentially invalid for Trakt; AnimeAggregations excludes VNDB and generic website/social/adaptation relationships.

AnimeAPI's generator can also use live scrapers and an external Geckyzz API. Anime Mapping DB does **not** call those services. Hikka, Kaize, Nautiljon and Otak-Otaku identifiers may enter through AnimeAPI's already-published GitHub TSV, but this project does not scrape those sites itself.

The exact URLs and notes embedded into every evidence database are defined in `anime_mapping_db/config.py`.

When publishing or redistributing a compiled `mappings.db`, the TSV/JSONL release exports, or another derivative database, preserve applicable attribution, share-alike/database-license requirements and notices from upstream sources. If an upstream project's licensing changes, update this file and the source specification before publishing the next database release.
