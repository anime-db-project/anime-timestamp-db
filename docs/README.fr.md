> **Projet développé avec l'aide de l'IA.**

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <strong>Français</strong> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Outil autonome et base SQLite d'intervalles à ignorer dans les épisodes d'anime : génériques de début et de fin, récapitulatifs, aperçus et autres segments, avec provenance vérifiable.

## Fonctionnalités

- Association des intervalles à des titres et épisodes vérifiés par Anime Mapping DB.
- Conservation des observations valides non résolues sous leurs identifiants natifs.
- Consensus traçable sans compter plusieurs fois les miroirs d'une même source.
- Bases d'exécution et de preuves séparées, avec audits et sommes de contrôle.
- Import des données publiques et collecteurs API AniSkip / Anime Skip avec reprise.

## Sources de données

Les compilations utilisent des jeux de données publics et un instantané d'Anime Mapping DB. Deux collecteurs API enregistrent des checkpoints durables ; leurs observations validées peuvent être importées. Les détails sont documentés séparément.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — Intervalles publics fondés sur les ID MAL
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — Données de saut d'épisodes liées à IMDb
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — Intervalles AniDB et observations agrégées
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Intervalles natifs des épisodes Bahamut
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — Passerelle entre identifiants et numérotations d'épisodes
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — Identité stable des titres d'anime
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — Collecte API avec checkpoints persistants

Les enregistrements normalisés utilisent `amdb:<anchor_id>`. Les numéros d'épisodes entre fournisseurs ne sont associés que lorsqu'une correspondance est prouvée ; les observations ambiguës restent accessibles sous leur forme d'origine. [Contrat du schéma](../docs/SCHEMA.md).

## Démarrage rapide

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Utilisation

```bash
# Recherche avec l'identifiant stable du projet
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# Pour un ID externe, fournir la base de correspondances
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Intervalles natifs sans identité confirmée
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Bases de données et versions

Les builds ordinaires publient des artefacts GitHub Actions. Les versions GitHub sont créées par tag ou déclenchement manuel. Le lot contient `timestamps.db`, `timestamps-evidence.db`, les copies compressées, `manifest.json`, `audit.json`, `SHA256SUMS` et les avis nécessaires.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Ce projet est indépendant d'**anime-db-bot** et n'est pas requis par le bot. Vérifiez schéma, couverture et conditions des sources avant toute intégration ou redistribution.

## Documentation

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licence et attribution

Code sous Apache-2.0. Les données compilées restent soumises aux conditions des jeux de données et API d'origine. Certaines sources imposent des mentions particulières ou n'ont pas de licence explicite : consulter les avis. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
