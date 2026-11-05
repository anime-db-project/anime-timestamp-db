> **AI-assisted project:** Developed with the assistance of AI.

<p align="center">
  <strong>English</strong> · <a href="docs/README.ru.md">Русский</a> · <a href="docs/README.ja.md">日本語</a> · <a href="docs/README.de.md">Deutsch</a> · <a href="docs/README.es.md">Español</a> · <a href="docs/README.fr.md">Français</a> · <a href="docs/README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](DATA_LICENSE.md)

A standalone tool and SQLite dataset for anime episode skip intervals: openings, endings, recaps, previews and related segments, with traceable source evidence.

## Features

- Normalize source intervals to anime and episode identities verified by Anime Mapping DB.
- Keep unresolved but valid observations queryable under their original source identifiers.
- Combine independent observations into traceable consensus intervals without counting mirrors as independent votes.
- Publish compact runtime data separately from detailed evidence, audit results and checksums.
- Import supported bulk datasets and maintain checkpointed AniSkip / Anime Skip API collectors.

## Data sources

Bulk builds use public datasets and an Anime Mapping DB snapshot. Two API collectors have durable checkpoints; validated snapshots may be imported by build and release workflows. API credentials and crawler-state details are documented separately.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — MAL-based bulk timestamp intervals
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — IMDb-linked episode skip data
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — AniDB-linked timestamps and source aggregates
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Bahamut source-native episode intervals
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — episode ID/numbering bridge
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — stable anime identity
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — checkpointed API collection

Normalized records use the shared `amdb:<anchor_id>` identity. Cross-provider episode numbers are accepted only with verified mappings; incompatible or ambiguous observations remain source-only instead of being guessed. [Schema](docs/SCHEMA.md).

## Quick start

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Usage

```bash
# Lookup using the project's stable anime identity
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# For a provider ID, supply the mapping database
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Source-specific intervals without proven cross-database identity
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Database and releases

Normal database builds publish downloadable GitHub Actions artifacts. Tagged or manually dispatched release builds publish GitHub Releases. Typical outputs include `timestamps.db`, `timestamps-evidence.db`, compressed copies, `manifest.json`, `audit.json`, `SHA256SUMS`, and required notices.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

This project is independent of **anime-db-bot** and is not required by the bot. Its schema, input coverage and upstream usage terms should be checked before integration or redistribution.

## Documentation

- [Schema and resolver contract](docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](docs/CRAWLING.md)
- [API source notice](ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](DATA_LICENSE.md) · [Third-party notices](THIRD_PARTY_NOTICES.md)

## License and attribution

Code: Apache-2.0. Compiled data is subject to upstream dataset and API terms. Some sources have special attribution or no explicit published data license; consult the notices before redistributing compiled artifacts. [Apache-2.0](LICENSE) · [DATA_LICENSE.md](DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
