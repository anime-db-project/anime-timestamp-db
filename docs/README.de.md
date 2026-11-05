> **KI-unterstütztes Projekt:** Dieses Projekt wurde mit Hilfe von KI entwickelt.

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <strong>Deutsch</strong> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Ein eigenständiges SQLite-Projekt für überspringbare Anime-Segmente wie Openings, Endings, Rückblicke und Vorschauen mit nachvollziehbarer Datenherkunft.

## Funktionen

- Zuordnung zu Titeln und Folgen anhand bestätigter Anime-Mapping-DB-Identitäten.
- Gültige, noch nicht zuordenbare Beobachtungen bleiben über Quell-IDs abrufbar.
- Nachvollziehbare Konsensintervalle ohne doppelte Gewichtung von Spiegelquellen.
- Separate Laufzeit- und Evidenzdatenbanken mit Audits und Prüfsummen.
- Import öffentlicher Datensätze sowie fortsetzbare AniSkip-/Anime-Skip-API-Sammler.

## Datenquellen

Reguläre Builds verwenden öffentliche Datensätze und einen Snapshot von Anime Mapping DB. Zwei API-Sammler speichern dauerhafte Checkpoints; geprüfte Daten können in Builds und Releases übernommen werden. Details stehen in der Crawling-Dokumentation.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — Öffentliche Intervalle mit MAL-Kennungen
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — IMDb-verknüpfte Skip-Daten für Folgen
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — AniDB-Zeitstempel und aggregierte Beobachtungen
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Bahamut-spezifische Folgenintervalle
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — Brücke für Folgenkennungen und Nummerierung
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — Stabile Anime-Titelidentität
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — API-Sammlung mit gespeicherten Checkpoints

Normalisierte Titel verwenden `amdb:<anchor_id>`. Folgennummern verschiedener Anbieter werden nur bei nachgewiesener Identität verknüpft; unklare Angaben bleiben quellenspezifisch. [Schemaspezifikation](../docs/SCHEMA.md).

## Schnellstart

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Verwendung

```bash
# Suche über die stabile Projektkennung
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# Bei externen IDs die Mapping-Datenbank angeben
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Quellspezifische Intervalle ohne bestätigte Identität
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Datenbanken und Releases

Normale Builds veröffentlichen GitHub-Actions-Artefakte. Releases entstehen über Tags oder manuell. Enthalten sind `timestamps.db`, `timestamps-evidence.db`, komprimierte Versionen, `manifest.json`, `audit.json`, `SHA256SUMS` und Quellenhinweise.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Das Projekt ist von **anime-db-bot** unabhängig und keine erforderliche Bot-Abhängigkeit. Vor Integration oder Weitergabe sind Schema, Datenabdeckung und Quellbedingungen zu prüfen.

## Dokumentation

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Lizenz und Quellenangaben

Der Code steht unter Apache-2.0. Für kompilierte Daten gelten die Bedingungen der Ursprungsquellen. Einige Quellen verlangen besondere Hinweise oder haben keine ausdrücklich veröffentlichte Datenlizenz. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
