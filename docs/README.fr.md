> **Projet développé avec l'aide de l'IA.**

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <strong>Français</strong> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Outil autonome et base SQLite d'intervalles à ignorer dans les épisodes d'anime : génériques de début et de fin, récapitulatifs, aperçus et autres segments, avec provenance vérifiable.

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## La base en chiffres

**57,795 épisodes normalisés · 217,288 intervalles · 126,831 consensus**

Ces nombres mesurent des choses différentes et ne se cumulent pas comme des titres. Les plages natives non résolues restent consultables mais ne sont pas comptées comme épisodes normalisés.

| Indicateur | Valeur |
| --- | ---: |
| Titres AMDB avec intervalles | **4,377** |
| Épisodes normalisés | **57,795** |
| Intervalles associés | **217,288** |
| Plages non résolues | **49,013** |
| Intervalles de consensus | **126,831** |
| Membres des consensus | **187,452** |
| Enregistrements de preuves | **307,672** |
| Snapshots de sources | **8** |
| Taille SQLite | **54.2 MiB** |
| SQLite compressée | **14.5 MiB** |

### Performance des recherches locales

**Intervalles sources**

| Indicateur | Valeur |
| --- | ---: |
| Médiane | **0.571 ms** |
| p95 | **0.618 ms** |
| p99 | **0.645 ms** |
| Requêtes séquentielles/s | **1,734** |

**Intervalles de consensus**

| Indicateur | Valeur |
| --- | ---: |
| Médiane | **0.535 ms** |
| p95 | **0.562 ms** |
| p99 | **0.597 ms** |
| Requêtes séquentielles/s | **1,858** |

Lectures séquentielles sur SQLite publiée avec cache chaud, Linux / Python 3.12 ; 250 épisodes × 2 tours. Ce n'est pas la latence réseau/API.

Instantané de version: **2026-11-05**, [v2026.11.05.10](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.05.10). [Manifeste actuel](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

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

## Couverture et normalisation

Les sources emploient des ID de titre, des numérotations et des couvertures différentes. Un intervalle correct ne prouve pas la même série chez MAL et AniList. Le constructeur distingue observations normalisées, propres à une source et rejetées, au lieu de créer de fausses équivalences.

- Données publiques AniSkip : titre MAL et épisode ; seules les identités AMDB confirmées sont normalisées.
- SkipDB : segments liés à IMDb, nécessitant AniBridge et Anime Mapping DB pour reconnaître l'unité de lecture.
- Open Anime Timestamps : observations AniDB et regroupements sans multiplier les votes de consensus.
- Baha Anime Skip : épisodes natifs `videoSn` sans inventer de numérotation MAL/AniList.
- API AniSkip et Anime Skip : checkpoints validés utilisables après examen des conditions de redistribution.

## Identité des titres et épisodes

Les titres tirent leur identité d'Anime Mapping DB. Une œuvre normalisée porte `anchor_id`, représenté par `amdb:<anchor_id>`. La base de temps ne duplique pas tous les alias externes. Les recherches `mal`, `anilist`, `anidb` exigent de fournir une `mappings.db` distincte.

L'épisode requiert une preuve distincte : épisode 1 peut désigner des contenus différents selon le service. Fournisseur, scope et numéro doivent être vérifiés. Les épisodes fractionnaires comme 12.5, spéciaux ou films ne sont pas regroupés ou arrondis au hasard. Les rapports AniBridge de découpage/fusion restent distincts.

Quand le titre est identifié sans équivalence d'épisode fiable, `source_title_refs` lie la clé native à l'ancre AMDB et `source_segments` conserve les plages sous leur référence initiale.

```text
anime-mapping-db (verified amdb:<anchor_id>)
       │
       └── anime-timestamp-db
              titles → episodes → segments
                 │                 │
        source_title_refs        consensus
                 │
            source_segments
```

## Schéma runtime et preuves

La base compacte `timestamps.db` sert les applications : `titles` pour les anchors AMDB, `episodes` pour les unités de lecture, `episode_ids` pour les numérotations prouvées, `episode_refs` pour les références de source et `segments` pour les intervalles normalisés.

`source_segments` garde les intervalles non résolus. `source_title_refs` ne contient que des références natives validées, pas tout le graphe d'alias. `consensus_segments` et `consensus_members` conservent les plages produites et leurs contributeurs ; `sources` et `lineages` distinguent l'origine et son indépendance.

| Table ou fichier | Rôle |
| --- | --- |
| `titles` | Identité AMDB stable |
| `episodes` | Unité de lecture vérifiée |
| `episode_ids` | Numérotation par fournisseur |
| `episode_refs` | Référence d'épisode d'origine |
| `segments` | Intervalles normalisés |
| `source_segments` | Plages non résolues |
| `sources / lineages` | Sources et lignées indépendantes |
| `consensus_segments / consensus_members` | Consensus et contributeurs |
| `timestamps-evidence.db` | Provenance et décisions |

`timestamps-evidence.db` stocke snapshots, empreintes, décisions de normalisation et plages originales. Elle sert les audits et la traçabilité plutôt que les requêtes de lecture courantes. Les durées sont en millisecondes entières.

## Consensus et provenance

Un consensus est matérialisé séparément des observations originales par une médiane pondérée. La tolérance, la fiabilité de correspondance et l'indépendance des lignées comptent ; les miroirs ne votent pas deux fois. Les lignes exclues restent consultables.

La tolérance par défaut est de 5 secondes et se modifie avec `--consensus-tolerance-ms`. Une plage consensuelle ne garantit pas un montage identique sur chaque diffuseur.

## Démarrage rapide

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Ligne de commande

La CLI crée les schémas, construit, inspecte, audite et interroge les données normalisées ou natives. `lookup` utilise `--episode` ou `--episode-key`, filtre par source et accepte le consensus. Pour les IDs hors AMDB, fournir `mappings.db`.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
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

## Intégration Python

`TimestampResolver` lit intervalles et consensus à partir d'un anchor AMDB ou d'un ID externe prouvé. Il sait également rechercher les enregistrements propres à une source sans équivalence sûre d'épisode. Conservez la base des mappings pour les IDs externes.

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver(
    "artifacts/timestamps.db",
    mapping_path="mappings.db",
)

# Known provider title / episode number
segments = resolver.get_segments_by_episode("mal", "5114", 1)

# Verified AMDB identity and concrete episode key
key = resolver.episode_key("amdb", "18472", 1)
consensus = resolver.get_consensus_by_anchor("amdb:18472", key) if key else []
```

## Exemples d'utilisation de la base

Les fichiers SQLite publiés peuvent être utilisés sans crawler, clé API ni compilation locale :

- **Lecteurs vidéo.** Proposer des actions pour ignorer génériques, récapitulatifs ou aperçus.
- **Catalogues d'anime.** Afficher les plages d'un épisode, leurs sources et leur consensus.
- **Bots et applications.** Interroger à partir d'un ID AMDB ou MAL/AniList/AniDB confirmé.
- **Outils hors ligne.** Embarquer un instantané SQLite consultable sans service externe.
- **Vérification.** Comparer les observations d'origine, les plages non résolues et les consensus.

Téléchargez les bases publiées. `timestamps.db` suffit pour les ID AMDB ; ajoutez une version compatible de `mappings.db` pour les IDs de fournisseurs :

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

Après installation du paquet (`python -m pip install -e .`), utilisez `TimestampResolver` pour consulter séparément les données brutes et le consensus :

```python
from anime_timestamp_db import TimestampResolver

resolver = TimestampResolver("timestamps.db", mapping_path="mappings.db")

# Use a verified MAL title ID and its own episode numbering.
segments = resolver.get_segments_by_episode("mal", "5114", 1)
key = resolver.episode_key("mal", "5114", 1)
consensus = resolver.get_consensus("mal", "5114", key) if key else []

for segment in segments:
    print(segment.segment_type, segment.start_ms / 1000, segment.end_ms / 1000)
for segment in consensus:
    print("consensus", segment.segment_type, segment.start_ms, segment.end_ms)
```

SQLite peut aussi être interrogé directement depuis divers langages. Exemple par ID AMDB et clé d'épisode :

```python
import sqlite3

with sqlite3.connect("file:timestamps.db?mode=ro", uri=True) as db:
    intervals = db.execute("""
        SELECT ep.episode_key, seg.segment_type, seg.start_ms,
               seg.end_ms, src.source_key
        FROM episodes AS ep
        JOIN segments AS seg ON seg.episode_id = ep.id
        JOIN sources AS src ON src.id = seg.source_id
        WHERE ep.anchor_id = ? AND ep.episode_key = ?
        ORDER BY seg.start_ms
    """, (18472, "ep:1")).fetchall()

for interval in intervals:
    print(interval)
```

Remplacez les ID d'exemple par des valeurs présentes. `start_ms` et `end_ms` sont en **millisecondes entières** : divisez par 1000 pour un lecteur qui utilise des secondes. Un titre dans Mapping DB ne possède pas forcément des plages.

Les observations non résolues sont accessibles par `source-lookup` ou `source-anchor`. Une clé d'épisode native n'est pas automatiquement le numéro MAL/AniList.

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

Vérifiez la compatibilité des versions, les manifestes et SHA-256. La version des timestamps enregistre l'empreinte exacte de Mapping DB utilisée.

## Collecte API et imports

Deux collecteurs interrogent AniSkip v2 (MAL/épisode) et Anime Skip GraphQL (AniList/épisodes). Limites de débit, checkpoints et reprise permettent une collecte durable. Une réponse sur un épisode ne prouve pas que les suivants aient tous été vérifiés.

Les branches publiques `crawler-state-aniskip` et `crawler-state-anime_skip` conservent l'état entre jobs. Les workflows n'importent les snapshots que si les deux points de contrôle existent et sont valides ; les instantanés partiels sont exclus.

Anime Skip utilise le secret `ANIME_SKIP_CLIENT_ID`. L'accès API ne vaut pas autorisation de redistribution. L'import local nécessite `--api-checkpoint-dir` et la confirmation `--allow-api-redistribution`, en tenant compte des notices.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Bases de données et versions

Les téléchargements durables sont publiés dans GitHub Releases (tags ou déclenchements manuels). Chaque version contient `timestamps.db`, `timestamps-evidence.db`, les fichiers compressés, `manifest.json`, `audit.json`, `performance.json`, `SHA256SUMS` et les notices.

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Ce projet est indépendant d'**anime-db-bot** et n'est pas requis par le bot. Vérifiez schéma, couverture et conditions des sources avant toute intégration ou redistribution.

## Fichiers distribués

GitHub Releases est le canal de téléchargement des bases. Runtime et preuves restent séparés. `manifest.json` décrit les sources, le mapping, les schémas et les tailles ; `audit.json` fournit les contrôles et `performance.json` les mesures locales de consultation.

| Table ou fichier | Rôle |
| --- | --- |
| `timestamps.db` | SQLite runtime compacte |
| `timestamps-evidence.db` | SQLite de preuves détaillées |
| `*.db.zst` | Distributions compressées |
| `manifest.json` | Sources, versions, tailles et empreintes |
| `audit.json` | Rapport d'audit |
| `SHA256SUMS` | Sommes SHA-256 |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Notices de licences et attribution |

## Audit et reproductibilité

Chaque build contrôle intégrité SQLite, clés étrangères, intervalles, références de titres et épisodes, membres du consensus et couverture non vide. Les formes intermédiaires strictes et les distributions compactes sont auditées pour exclure les correspondances refusées.

URLs, SHA-256, tailles et métadonnées des entrées sont enregistrées. Une version contrôlée d'Anime Mapping DB est utilisée localement. Le manifest est la référence pour les chiffres et tailles courants.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Limites d'intégration

Projet indépendant d'anime-db-bot, il n'est pas requis par celui-ci. Les builds ordinaires ne parcourent pas les plateformes de streaming et ne garantissent ni des plages pour tous les titres ni des correspondances d'épisode incertaines.

## Documentation

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licence et attribution

Code sous Apache-2.0. Les données compilées restent soumises aux conditions des jeux de données et API d'origine. Certaines sources imposent des mentions particulières ou n'ont pas de licence explicite : consulter les avis. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
