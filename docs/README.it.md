> **Progetto sviluppato con l'aiuto dell'IA.**

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <strong>Italiano</strong>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Strumento indipendente e database SQLite di segmenti saltabili degli episodi anime — opening, ending, riepiloghi e anteprime — con provenienza verificabile.

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## Il database in numeri

**58,981 episodi normalizzati · 243,684 intervalli · 134,701 consensi**

Sono metriche diverse, da non sommare come titoli o scene. Gli intervalli nativi non risolti sono consultabili ma non contano come episodi normalizzati.

| Indicatore | Valore |
| --- | ---: |
| Titoli AMDB con intervalli | **4,660** |
| Episodi normalizzati | **58,981** |
| Intervalli associati | **243,684** |
| Intervalli nativi non risolti | **78,367** |
| Intervalli di consenso | **134,701** |
| Collegamenti del consenso | **213,765** |
| Record di prova | **363,729** |
| Snapshot delle fonti | **8** |
| Dimensione SQLite | **65.9 MiB** |
| SQLite compresso | **16.9 MiB** |

### Prestazioni delle query locali

**Intervalli delle fonti**

| Indicatore | Valore |
| --- | ---: |
| Mediana | **0.773 ms** |
| p95 | **1.105 ms** |
| p99 | **1.311 ms** |
| Query sequenziali/s | **1,240** |

**Intervalli di consenso**

| Indicatore | Valore |
| --- | ---: |
| Mediana | **0.716 ms** |
| p95 | **0.743 ms** |
| p99 | **0.779 ms** |
| Query sequenziali/s | **1,394** |

Query sequenziali con cache calda sulla SQLite pubblicata, Linux / Python 3.12; 250 episodi × 2 round. Non misura la latenza API.

Snapshot della release: **2026-11-13**, [v2026.11.13.29](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.13.29). [Manifest attuale](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

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

## Copertura e normalizzazione

Le fonti usano ID, numerazioni e coperture differenti. Un intervallo valido non dimostra che sia lo stesso episodio in MAL e AniList. Il builder distingue osservazioni normalizzate, native e scartate, evitando corrispondenze inventate.

- Dataset pubblico AniSkip: tempi basati su ID MAL ed episodio; si normalizzano solo gli anchor AMDB confermati.
- SkipDB: intervalli collegati a IMDb; AniBridge e Anime Mapping DB devono provare la corretta unità di riproduzione.
- Open Anime Timestamps: osservazioni AniDB e aggregati senza voti duplicati nel consenso.
- Baha Anime Skip: episodi nativi `videoSn` senza creare numerazioni MAL/AniList fittizie.
- API AniSkip e Anime Skip: checkpoint validati possono integrare i dati pubblici, rispettando i permessi.

## Identità di titoli ed episodi

La fonte dell'identità dei titoli è Anime Mapping DB. Il titolo normalizzato usa `anchor_id`, pubblicamente `amdb:<anchor_id>`. I timestamp non duplicano il grafo completo degli ID esterni. Le richieste `mal`, `anilist`, `anidb` ecc. richiedono una `mappings.db` separata.

Gli episodi hanno identità più rigorose: episodio 1 può significare parti diverse su due servizi. Provider, scope e numero richiedono prove. Frazioni come 12.5, speciali e film non vengono arrotondati o uniti arbitrariamente. I mapping AniBridge divisi/accorpati restano distinti.

Se il titolo è verificato ma non l'episodio, `source_title_refs` collega l'ID della fonte all'anchor AMDB e `source_segments` conserva gli intervalli originali senza inventare un episodio canonico.

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

## Schema runtime e prove

La compatta `timestamps.db` serve le app. `titles` contiene anchor AMDB; `episodes`, unità di riproduzione; `episode_ids`, numerazioni confermate; `episode_refs`, riferimenti nativi; `segments`, osservazioni normalizzate.

`source_segments` conserva intervalli non risolti. `source_title_refs` registra solo riferimenti verificati, non l'intero grafo di alias. `consensus_segments` e `consensus_members` mostrano le proposte e i loro elementi; `sources` e `lineages` distinguono la fonte dalla provenienza indipendente.

| Tabella o file | Scopo |
| --- | --- |
| `titles` | Identità AMDB stabile |
| `episodes` | Unità di riproduzione verificata |
| `episode_ids` | Numerazione episodi per provider |
| `episode_refs` | Riferimenti nativi a episodi |
| `segments` | Intervalli normalizzati |
| `source_segments` | Intervalli nativi non risolti |
| `sources / lineages` | Fonti e linee indipendenti |
| `consensus_segments / consensus_members` | Consenso e osservazioni |
| `timestamps-evidence.db` | Provenienza e decisioni |

`timestamps-evidence.db` mantiene snapshot, hash, decisioni di normalizzazione e intervalli originali. È dedicata a tracciabilità e audit, non alle normali query di riproduzione. I tempi sono memorizzati in millisecondi interi.

## Consenso e provenienza

Il consenso viene calcolato a parte con una mediana ponderata senza sovrascrivere le osservazioni. Considera tolleranza, affidabilità e indipendenza della fonte, evitando doppi voti di mirror. I dati non eleggibili restano consultabili.

La tolleranza predefinita dei confini è 5 secondi, modificabile con `--consensus-tolerance-ms`. Il consenso resta una proposta e non garantisce tempi identici in tutte le versioni video.

## Avvio rapido

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Interfaccia a riga di comando

La CLI crea schemi, costruisce, ispeziona, verifica e cerca intervalli normalizzati o nativi. `lookup` accetta `--episode` oppure `--episode-key`, può filtrare la fonte o usare il consenso. Gli ID esterni richiedono `mappings.db`.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
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

## Integrazione Python

`TimestampResolver` recupera intervalli e consenso per anchor AMDB o ID esterno verificato. Supporta anche dati nativi non normalizzabili in sicurezza. Se l'app usa ID esterni, conserva anche il database mapping.

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

## Modi per utilizzare il database

Il file SQLite pubblicato è utilizzabile senza collector, API key o compilazioni:

- **Player video.** Offrire pulsanti per saltare opening, ending, riepiloghi e anteprime.
- **Cataloghi anime.** Mostrare intervalli e concordanza delle fonti sulla timeline.
- **Bot e app.** Recuperare intervalli per ID AMDB o MAL/AniList/AniDB verificato.
- **Programmi offline.** Distribuire uno snapshot SQLite per ricerche locali senza rete.
- **Audit e analisi.** Confrontare osservazioni originali, intervalli non risolti e consenso.

Scarica i database pubblicati. Per ID AMDB basta `timestamps.db`; per ID esterni serve anche un `mappings.db` compatibile:

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

Installa il pacchetto (`python -m pip install -e .`) e usa `TimestampResolver` per leggere osservazioni e consenso:

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

SQLite può essere interrogato direttamente da qualsiasi linguaggio. Esempio per anchor AMDB e chiave episodio:

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

Sostituisci i valori di esempio con ID effettivamente presenti. `start_ms` e `end_ms` sono **millisecondi interi**: dividi per 1000 per player che usano secondi. La presenza di un titolo in Mapping DB non garantisce timestamp.

Le osservazioni non risolte sono consultabili con `source-lookup` e `source-anchor`. Le chiavi episodio native non vanno equiparate automaticamente a MAL/AniList.

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

Usa versioni compatibili e verifica manifest e SHA-256. La release timestamp registra l'hash esatto di Mapping DB usato.

## Raccolta API e importazione

Due collector interrogano AniSkip v2 (MAL/episodio) e Anime Skip GraphQL (AniList/episodi). I limiti di velocità e i checkpoint consentono ripresa dopo interruzioni. Una risposta per i primi episodi non equivale a copertura completa dei successivi.

I branch pubblici `crawler-state-aniskip` e `crawler-state-anime_skip` conservano lo stato fra i job. Le release importano soltanto se entrambi i checkpoint sono validi, escludendo dati parziali.

Anime Skip usa il segreto `ANIME_SKIP_CLIENT_ID`. L'accesso API non autorizza automaticamente la redistribuzione. L'import locale richiede `--api-checkpoint-dir` e `--allow-api-redistribution` come conferma esplicita dei permessi.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Database e release

I file permanenti vengono pubblicati su GitHub Releases tramite tag o esecuzione manuale. Ogni release include `timestamps.db`, `timestamps-evidence.db`, versioni compresse, `manifest.json`, `audit.json`, `performance.json`, `SHA256SUMS` e avvisi delle fonti.

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Il progetto è indipendente da **anime-db-bot** e non è una dipendenza necessaria. Prima dell'integrazione o ridistribuzione verificare schema, copertura e termini delle fonti.

## File distribuiti

GitHub Releases è il canale di download delle basi. Runtime ed evidence restano separati. `manifest.json` contiene fonti, fingerprint mapping, schema e dimensioni; `audit.json` riporta i controlli e `performance.json` i benchmark delle query locali.

| Tabella o file | Scopo |
| --- | --- |
| `timestamps.db` | SQLite runtime compatta |
| `timestamps-evidence.db` | SQLite per evidenze dettagliate |
| `*.db.zst` | Versioni compresse |
| `manifest.json` | Fonti, schema, dimensioni e hash |
| `audit.json` | Risultati dell'audit |
| `SHA256SUMS` | Checksum SHA-256 |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Avvisi di licenza e attribuzione |

## Audit e riproducibilità

Ogni build verifica integrità SQLite, chiavi esterne, intervalli validi, riferimenti a titoli ed episodi, partecipanti al consenso e copertura reale. Si controllano sia staging rigoroso sia distribuzioni compatte, escludendo mapping rifiutati.

Si registrano URL, SHA-256, dimensioni e metadati dei download. Viene usato localmente un preciso snapshot verificato di Anime Mapping DB. Conteggi e dimensioni attuali sono nel manifest e non in valori fissi nel README.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Limiti d'integrazione

Il progetto è indipendente da anime-db-bot e non è obbligatorio per il bot. Le build normali non visitano siti di streaming, non garantiscono dati per ogni titolo e non forzano associazioni di episodi dubbie.

## Documentazione

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licenza e attribuzioni

Codice sotto Apache-2.0. I dati compilati seguono i termini dei dataset e delle API di origine. Alcune fonti richiedono attribuzioni speciali o non pubblicano una licenza esplicita: consultare gli avvisi. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
