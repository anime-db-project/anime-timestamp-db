> **Progetto sviluppato con l'aiuto dell'IA.**

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <strong>Italiano</strong>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Strumento indipendente e database SQLite di segmenti saltabili degli episodi anime — opening, ending, riepiloghi e anteprime — con provenienza verificabile.

## Funzionalità

- Collegamento a titoli ed episodi verificati tramite Anime Mapping DB.
- Le osservazioni valide non risolte rimangono consultabili tramite ID della fonte.
- Consenso tracciabile fra osservazioni indipendenti, evitando doppi voti dei mirror.
- Database runtime e prove separati, con audit e checksum.
- Import di dataset pubblici e raccolta API AniSkip / Anime Skip riprendibile.

## Fonti dei dati

Le build ordinarie utilizzano file pubblici e uno snapshot di Anime Mapping DB. Due collector API salvano checkpoint duraturi; i dati validati possono essere importati nelle build e nelle release. I dettagli sono descritti a parte.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — Intervalli pubblici basati sugli ID MAL
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — Dati di salto degli episodi collegati a IMDb
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — Intervalli AniDB e osservazioni aggregate
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Intervalli nativi degli episodi Bahamut
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — Ponte fra ID e numerazioni degli episodi
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — Identità stabile dei titoli anime
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — Raccolta API con checkpoint persistenti

I record normalizzati usano `amdb:<anchor_id>`. La numerazione degli episodi fra servizi viene collegata solo quando verificata; i casi ambigui restano consultabili nella forma originale. [Specifica dello schema](../docs/SCHEMA.md).

## Avvio rapido

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Utilizzo

```bash
# Ricerca con l'ID stabile del progetto
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# Per un ID esterno passa il database di mapping
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Intervalli specifici della fonte senza identità verificata
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Database e release

Le build normali pubblicano artefatti GitHub Actions. Le release permanenti si creano tramite tag o avvio manuale. I file comprendono `timestamps.db`, `timestamps-evidence.db`, copie compresse, `manifest.json`, `audit.json`, `SHA256SUMS` e avvisi richiesti.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Il progetto è indipendente da **anime-db-bot** e non è una dipendenza necessaria. Prima dell'integrazione o ridistribuzione verificare schema, copertura e termini delle fonti.

## Documentazione

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licenza e attribuzioni

Codice sotto Apache-2.0. I dati compilati seguono i termini dei dataset e delle API di origine. Alcune fonti richiedono attribuzioni speciali o non pubblicano una licenza esplicita: consultare gli avvisi. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
