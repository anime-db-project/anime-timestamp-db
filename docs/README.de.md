> **KI-unterstütztes Projekt:** Dieses Projekt wurde mit Hilfe von KI entwickelt.

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <strong>Deutsch</strong> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Ein eigenständiges SQLite-Projekt für überspringbare Anime-Segmente wie Openings, Endings, Rückblicke und Vorschauen mit nachvollziehbarer Datenherkunft.

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## Datenbank in Zahlen

**59,072 normalisierte Folgen · 245,952 zugeordnete Intervalle · 134,975 Konsensintervalle**

Dies sind separate Kennzahlen und keine addierbaren Titelzahlen. Quelleneigene Bereiche bleiben abrufbar, gelten aber nicht als normalisierte Episoden.

| Kennzahl | Wert |
| --- | ---: |
| AMDB-Titel mit Zeitstempeln | **4,674** |
| Normalisierte Folgen | **59,072** |
| Zugeordnete Intervalle | **245,952** |
| Quelleneigene Intervalle | **78,381** |
| Konsensintervalle | **134,975** |
| Konsensmitgliedschaften | **216,033** |
| Evidenzrecords | **366,238** |
| Quell-Snapshots | **8** |
| SQLite-Größe | **66.3 MiB** |
| Komprimierte SQLite-Größe | **17.0 MiB** |

### Lokale Abfrageleistung

**Quellintervalle**

| Kennzahl | Wert |
| --- | ---: |
| Median | **0.795 ms** |
| p95 | **0.893 ms** |
| p99 | **1.347 ms** |
| Sequentielle Abfragen/s | **1,229** |

**Konsensintervalle**

| Kennzahl | Wert |
| --- | ---: |
| Median | **0.732 ms** |
| p95 | **0.773 ms** |
| p99 | **0.798 ms** |
| Sequentielle Abfragen/s | **1,357** |

Sequentielle Abfragen auf Release-SQLite mit warmem Cache, Linux / Python 3.12; 250 Folgen × 2 Runden. Keine API-/Netzwerklatenz.

Release-Snapshot: **2026-11-14**, [v2026.11.14.30](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.14.30). [Aktuelles Manifest](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

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

## Quellenabdeckung und Normalisierung

Die Quellen verwenden verschiedene Titelkennungen, Folgennummerierungen und Abdeckungsgrade. Ein gültiges Intervall beweist nicht automatisch dieselbe Folge bei MAL und AniList. Der Builder unterscheidet normalisierte, quellenspezifische und verworfene Beobachtungen.

- AniSkip-Öffentlichdaten: MAL-Titel und Episoden; nur geprüfte AMDB-Anker werden normalisiert.
- SkipDB: IMDb-verknüpfte Abschnitte werden über AniBridge und Anime Mapping DB einer konkreten Folge zugeordnet.
- Open Anime Timestamps: AniDB-Daten und Aggregationen ohne doppelte Konsensstimmen.
- Baha Anime Skip: Bahamut-eigene `videoSn`-Folgen ohne erfundene MAL-/AniList-Folgenidentitäten.
- AniSkip-/Anime-Skip-APIs: verifizierte Checkpoints können die Bulk-Daten unter Beachtung der Rechte ergänzen.

## Titel- und Folgenidentität

Anime Mapping DB liefert die Titelidentität. Normale Titel tragen `anchor_id` beziehungsweise `amdb:<anchor_id>`. Die Timestamp-Datenbank kopiert nicht den gesamten externen ID-Graphen. Für `mal`, `anilist`, `anidb` usw. kann eine separate `mappings.db` eingebunden werden.

Die Folge ist eine eigenständige Identität: Folge 1 kann bei zwei Anbietern unterschiedliche Inhalte bedeuten. Anbieter, Scope und Nummer müssen belegt sein. Bruchteile wie 12.5, Specials und Filme werden nicht gerundet oder willkürlich verbunden. Split-/Merge-Verhältnisse von AniBridge bleiben erhalten.

Wenn der Titel bekannt, die Folge jedoch nicht sicher zuordenbar ist, kann `source_title_refs` den AMDB-Anker belegen und `source_segments` die Abschnitte unter Originalkennungen behalten.

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

## Runtime- und Evidenzschema

Die kompakte `timestamps.db` ist für Anwendungen gedacht. `titles` speichert AMDB-Anker, `episodes` Wiedergabeeinheiten, `episode_ids` belegte Anbieterfolgen, `episode_refs` Quellverweise und `segments` normalisierte Abschnitte.

`source_segments` hält gültige, aber noch nicht normalisierte Bereiche. `source_title_refs` enthält nur bestätigte native Titelreferenzen. `consensus_segments` und `consensus_members` dokumentieren Konsens und Bestandteile. `sources` und `lineages` unterscheiden Datensatz und unabhängige Herkunft.

| Tabelle oder Datei | Rolle |
| --- | --- |
| `titles` | Stabile AMDB-Titelidentität |
| `episodes` | Verifizierte Wiedergabeeinheit |
| `episode_ids` | Anbieterbezogene Folgennummern |
| `episode_refs` | Originalfolgen der Quellen |
| `segments` | Normalisierte Zeitintervalle |
| `source_segments` | Quelleneigene unklare Intervalle |
| `sources / lineages` | Quellen und unabhängige Linien |
| `consensus_segments / consensus_members` | Konsens und beteiligte Beobachtungen |
| `timestamps-evidence.db` | Herkunft und Entscheidungen |

`timestamps-evidence.db` speichert Ursprungsdateien, Hashes, Normalisierungsentscheidungen und ursprüngliche Zeitbereiche. Sie dient Audit und Reproduzierbarkeit, nicht dem üblichen Playback-Lookup. Alle Zeitwerte sind ganze Millisekunden.

## Konsens und Herkunft

Konsens wird unabhängig von Originalbeobachtungen mit einem gewichteten Median errechnet. Toleranzen, Zuordnungsgewichte und unabhängige Datenherkunft werden berücksichtigt; Spiegel erhöhen nicht die Stimmenzahl. Ausgeschlossene Zeilen bleiben abfragbar.

Die Standardtoleranz für Abschnittsgrenzen beträgt 5 Sekunden; `--consensus-tolerance-ms` ändert sie. Konsens ist eine Empfehlung und keine Garantie für identische Schnittfassungen aller Streams.

## Schnellstart

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Kommandozeile

Das CLI erstellt Schemas, baut Datenbanken, zeigt Informationen, auditiert und sucht sowohl normalisierte als auch quelleneigene Abschnitte. `lookup` benötigt `--episode` oder `--episode-key`, unterstützt Quellenfilter und Konsensabfragen. Für fremde Titel-IDs ist `mappings.db` nötig.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
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

## Python-Integration

`TimestampResolver` kann per AMDB-Anker oder bestätigter Anbieterkennung Quellabschnitte und Konsens lesen. Nicht normalisierbare, aber gültige Bereiche sind ebenfalls abrufbar. Anwendungen mit externen Titel-IDs benötigen die Mapping-Datenbank daneben.

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

## Einsatzmöglichkeiten der Timestamp-Datenbank

Die veröffentlichte SQLite-Datei kann ohne Crawler, Build-Prozess oder API-Schlüssel genutzt werden:

- **Videoplayer.** Schaltflächen zum Überspringen von Opening, Ending, Rückblick oder Vorschau anzeigen.
- **Anime-Webseiten.** Folgen-Zeitachsen und übereinstimmende Quellen darstellen.
- **Bots und Apps.** Über AMDB oder bestätigte MAL-/AniList-/AniDB-Kennungen Quellenintervalle und Konsens abrufen.
- **Offline- und Mobilprogramme.** SQLite-Snapshot mitliefern und lokal ohne API-Anfragen lesen.
- **Audits.** Originalintervalle, nur quelleneigene Daten und Konsens nachvollziehen.

Die Laufzeitdatenbank kann direkt heruntergeladen werden. Für AMDB IDs genügt `timestamps.db`; für externe Anbieter-IDs braucht man zusätzlich eine kompatible `mappings.db`:

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

Nach Installation des Pakets (`python -m pip install -e .`) kann `TimestampResolver` die Originalintervalle und den Konsens getrennt liefern:

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

Direkte SQLite-Abfragen sind mit jeder geeigneten Programmiersprache möglich. Beispiel für normalisierte Bereiche anhand des AMDB-Ankers und Folgenschlüssels:

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

Die Beispiel-IDs durch tatsächliche Werte des Snapshots ersetzen. `start_ms` und `end_ms` sind **ganze Millisekunden**; für Player mit Sekunden durch 1000 teilen. Ein Titel in Mapping DB muss nicht in Timestamp DB enthalten sein.

Ungeklärte Beobachtungen bleiben über `source-lookup` und `source-anchor` erreichbar. Quellfolgen dürfen nicht automatisch mit MAL-/AniList-Folgen gleichgesetzt werden.

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

Bei gemeinsamer Nutzung kompatible Versionen, Manifeste und SHA-256 prüfen. Der Timestamp-Build hält den Hash der verwendeten Mapping DB fest.

## API-Sammlung und Release-Import

Unabhängige Sammler nutzen AniSkip v2 (MAL/Folge) und Anime Skip GraphQL (AniList/Titelfolgen). Rate Limits und dauerhafte Checkpoints erlauben die Wiederaufnahme. Spätere Folgen dürfen nicht als vollständig geprüft gelten, nur weil frühere Treffer haben.

Die öffentlichen Branches `crawler-state-aniskip` und `crawler-state-anime_skip` speichern Zustände zwischen Actions. Nur wenn beide Snapshots vorliegen und gültig sind, werden sie bei Build und Release importiert; Teilstände bleiben außen vor.

Anime Skip benötigt das geheime `ANIME_SKIP_CLIENT_ID`. API-Zugang bedeutet keine automatische Weiterverbreitungserlaubnis. Ein lokaler Import erfordert `--api-checkpoint-dir` und `--allow-api-redistribution` als ausdrückliche Bestätigung.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Datenbanken und Releases

Dauerhafte Datenbank-Downloads werden in GitHub Releases (Tags oder manuell) veröffentlicht. Jedes Release enthält `timestamps.db`, `timestamps-evidence.db`, komprimierte Varianten, `manifest.json`, `audit.json`, `performance.json`, `SHA256SUMS` und Quellenhinweise.

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Das Projekt ist von **anime-db-bot** unabhängig und keine erforderliche Bot-Abhängigkeit. Vor Integration oder Weitergabe sind Schema, Datenabdeckung und Quellbedingungen zu prüfen.

## Distributionsdateien

GitHub Releases ist der empfohlene Download-Kanal. Runtime- und Evidenzdaten bleiben getrennt. `manifest.json` beschreibt Quellen, Mapping-Fingerprint, Schema und Größen; `audit.json` enthält Prüfungen und `performance.json` reproduzierbare lokale Abfragemessungen.

| Tabelle oder Datei | Rolle |
| --- | --- |
| `timestamps.db` | Kompakte Laufzeit-SQLite |
| `timestamps-evidence.db` | Detaillierte Evidenz-SQLite |
| `*.db.zst` | Komprimierte Dateien |
| `manifest.json` | Quellen, Schema, Größen und Hashes |
| `audit.json` | Auditbericht |
| `SHA256SUMS` | SHA-256-Prüfsummen |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Lizenzen und Quellenhinweise |

## Audit und Reproduzierbarkeit

Jeder Build prüft SQLite-Integrität, Fremdschlüssel, gültige Intervalle, Titel-/Folgenbeziehungen, Konsensmitglieder und nicht leere Quelldaten. Strenge Zwischenformen und kompakte Distributionen werden kontrolliert; abgewiesene Zuordnungen dürfen nicht als normale Abschnitte erscheinen.

URL, SHA-256, Byteanzahl und Abrufdetails der Quellen werden gespeichert. Ein überprüfter Anime-Mapping-DB-Snapshot wird lokal verwendet. Aktuelle Mengen und Größen stehen im Manifest, nicht in festen README-Zahlen.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Integrationsgrenzen

Das Projekt ist unabhängig vom anime-db-bot und für ihn nicht verpflichtend. Normale Datenbank-Builds durchsuchen keine Streamingseiten, garantieren keine Abschnitte für jeden Titel und erzwingen keine unsicheren Folgenzuordnungen.

## Dokumentation

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Lizenz und Quellenangaben

Der Code steht unter Apache-2.0. Für kompilierte Daten gelten die Bedingungen der Ursprungsquellen. Einige Quellen verlangen besondere Hinweise oder haben keine ausdrücklich veröffentlichte Datenlizenz. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
