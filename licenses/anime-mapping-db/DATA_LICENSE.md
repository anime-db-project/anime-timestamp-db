# Data licensing

This document describes the licensing boundary between the Anime Mapping DB software and the generated mapping databases.

It is an informational project notice, not legal advice. The authoritative terms for third-party data remain the licenses and notices published by the upstream projects.

## Source code

The source code in this repository is licensed under the Apache License 2.0. See [`LICENSE`](LICENSE).

Apache-2.0 applies to the builder, importers, resolver, release tooling, tests, documentation, and other original software in this repository. It does **not** automatically relicense third-party datasets or the third-party data contained in generated database artifacts.

## Generated databases

The project generates artifacts such as:

- `mappings.db`;
- `mappings-evidence.db`;
- `mappings.tsv.zst`;
- `mappings.jsonl.zst`;
- other compressed or transformed release variants derived from the same data.

These files are compiled from multiple independent third-party datasets. Their data therefore remains subject to the applicable upstream database/content licenses, attribution requirements, share-alike requirements, and other notices.

Do not assume that a generated `mappings.db` is licensed solely under Apache-2.0 just because the software that built it is Apache-2.0.

## Important upstream license families

The current build includes or can include data under several licensing models:

### ODbL 1.0 + DbCL 1.0

Used by compiled datasets such as AnimeAPI and anime-offline-database, and by other database-oriented sources noted in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

ODbL is designed for databases and can impose attribution and share-alike obligations when a covered database or a derivative database is publicly redistributed. DbCL addresses the licensed database contents alongside ODbL.

Because Anime Mapping DB combines data from sources under these terms, redistribution of a generated database should preserve the applicable notices and satisfy any database-license obligations that apply to the resulting use or distribution.

### CC0 1.0

Some sources, including Wikidata structured data and the Rensetsu SilverYasha/AnimeThemes public dumps used by this project, are published under CC0. CC0 is intentionally permissive and is designed to waive applicable copyright/database rights to the extent possible.

### MIT / Apache-2.0 repositories

Several mapping repositories publish their software or repository contents under permissive licenses such as MIT or Apache-2.0. A repository-level software license does not necessarily erase licensing obligations inherited from data that the repository itself aggregates from other projects.

For that reason this project records both the immediate source and known upstream-data caveats instead of treating every public GitHub dataset as newly relicensed under the repository's software license.

### Sources without an explicit dataset license

Some upstream repositories, including `anime-and-manga/lists`, do not clearly declare a standalone license for their dataset. Public availability on GitHub does not itself grant unrestricted redistribution rights.

Anime Mapping DB therefore records these sources explicitly in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) rather than assigning them a license that their authors did not state.

## Redistribution guidance

If you redistribute `mappings.db`, `mappings-evidence.db`, a modified version of either database, or another database substantially derived from them:

1. keep this `DATA_LICENSE.md` notice with the distribution when practical;
2. keep [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and the relevant upstream attribution/license notices;
3. review the current upstream license terms for the datasets included in the specific build;
4. comply with applicable ODbL/DbCL attribution and share-alike requirements where they apply;
5. do not describe the complete generated database as simply "Apache-2.0" unless you have independently verified that such a statement is accurate for that particular distribution.

The release `manifest.json` records the concrete source datasets used for each build, including source URLs, hashes, importer names, record counts, and licensing notes. Use that manifest together with `THIRD_PARTY_NOTICES.md` when determining the provenance of a specific release.

## Project licensing summary

```text
Original Anime Mapping DB source code
    -> Apache-2.0

Third-party source datasets
    -> their respective upstream licenses and terms

Generated mappings.db / mappings-evidence.db
    -> compiled data artifact; redistribution remains subject to
       the applicable upstream data/database license obligations
```

For the current source-by-source licensing table, see [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
