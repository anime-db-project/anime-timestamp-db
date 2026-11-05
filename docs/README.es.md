> **Proyecto desarrollado con ayuda de IA.**

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <strong>Español</strong> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Herramienta independiente y base SQLite de segmentos saltables de anime — aperturas, cierres, resúmenes y avances — con evidencia rastreable.

## Funciones

- Vinculación de intervalos a títulos y episodios verificados por Anime Mapping DB.
- Las observaciones válidas sin correspondencia permanecen accesibles mediante IDs de origen.
- Consenso trazable entre observaciones independientes, sin contar espejos dos veces.
- Bases separadas de ejecución y evidencia, con auditorías y sumas de verificación.
- Importación de datasets públicos y recolectores API de AniSkip / Anime Skip reanudables.

## Fuentes de datos

Las compilaciones normales usan datos públicos y una instantánea de Anime Mapping DB. Dos recolectores API guardan puntos de control duraderos; las instantáneas verificadas pueden incorporarse a compilaciones y publicaciones. El proceso se explica por separado.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — Intervalos públicos basados en IDs de MAL
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — Datos de episodios relacionados con IMDb
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — Intervalos AniDB y observaciones agregadas
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Intervalos nativos de episodios Bahamut
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — Puente para IDs y numeración de episodios
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — Identidad estable de los títulos
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — Recolección API con puntos de control

Los registros normalizados emplean `amdb:<anchor_id>`. Los números de episodio de distintos proveedores se equiparan solo con pruebas; lo ambiguo se conserva con su identificación original. [Especificación del esquema](../docs/SCHEMA.md).

## Cobertura y normalización

Las fuentes usan distintos IDs, numeración de episodios y niveles de cobertura. Un intervalo válido no demuestra que sea el mismo episodio en MAL y AniList. El generador separa observaciones normalizadas, nativas y rechazadas, sin inventar identidades.

- AniSkip público: intervalos por título MAL y episodio; se normalizan solo anchors AMDB confirmados.
- SkipDB: tiempos vinculados a IMDb; AniBridge y Anime Mapping DB deben acreditar la unidad de reproducción.
- Open Anime Timestamps: registros AniDB y agregados, sin duplicar votos en el consenso.
- Baha Anime Skip: episodios nativos `videoSn`; no se inventan IDs de episodios MAL/AniList.
- API AniSkip y Anime Skip: puntos de control verificados pueden complementar los archivos públicos conforme a sus términos.

## Identidad de títulos y episodios

La identidad del título procede de Anime Mapping DB. Los registros normales usan `anchor_id`, expresado como `amdb:<anchor_id>`. La base de tiempos no copia todos los alias externos. Para consultas `mal`, `anilist`, `anidb`, etc., adjunte una `mappings.db` aparte.

La identidad de episodio es más estricta que la de título. Dos servicios pueden llamar episodio 1 a contenidos diferentes: proveedor, ámbito y número deben verificarse. Fracciones como 12.5, especiales y películas no se redondean ni fusionan por intuición. Se respetan las correspondencias divididas/combinadas de AniBridge.

Si se acredita el título pero no el número equivalente, `source_title_refs` conserva el vínculo AMDB y `source_segments` mantiene los intervalos bajo las claves originales, sin inventar una correspondencia canónica.

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

## Esquema runtime y de evidencia

La compacta `timestamps.db` está orientada a aplicaciones. `titles` contiene anchors AMDB; `episodes`, unidades de reproducción; `episode_ids`, numeraciones verificadas; `episode_refs`, referencias nativas; y `segments`, intervalos normalizados.

`source_segments` almacena rangos válidos sin resolver. `source_title_refs` contiene solo claves de origen verificadas, no todo el grafo de alias. `consensus_segments` y `consensus_members` conservan consensos y sus observaciones. `sources` y `lineages` separan origen e independencia.

| Tabla o archivo | Función |
| --- | --- |
| `titles` | Título AMDB estable |
| `episodes` | Unidad de reproducción verificada |
| `episode_ids` | Numeración por proveedor |
| `episode_refs` | Clave nativa de episodio |
| `segments` | Intervalos normalizados |
| `source_segments` | Rangos no resueltos |
| `sources / lineages` | Fuentes y linajes independientes |
| `consensus_segments / consensus_members` | Consenso y miembros |
| `timestamps-evidence.db` | Procedencia y decisiones |

`timestamps-evidence.db` contiene instantáneas, hashes, decisiones de normalización e intervalos originales. Se usa para auditar y reproducir resultados, no para búsquedas de reproducción habituales. Los tiempos se guardan como milisegundos enteros.

## Consenso y procedencia

El consenso se calcula sin sobrescribir las observaciones mediante mediana ponderada. Considera tolerancia, confianza y linajes independientes, sin contar espejos como múltiples votos. Los registros excluidos siguen disponibles para consulta.

La tolerancia predeterminada es de 5 segundos; se ajusta mediante `--consensus-tolerance-ms`. El consenso es una estimación y no garantiza idénticos intervalos en todas las ediciones de vídeo.

## Inicio rápido

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Interfaz de comandos

La CLI crea esquemas, compila, inspecciona, audita y consulta intervalos normalizados y nativos. `lookup` admite `--episode` o `--episode-key`, filtros por fuente y consenso. Los IDs de título externos requieren una `mappings.db` correspondiente.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Uso

```bash
# Consulta usando el ID estable del proyecto
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# Para un ID externo, facilite la base de correspondencias
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Intervalos de origen sin identidad confirmada
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Integración Python

`TimestampResolver` obtiene intervalos y consenso por anchor AMDB o ID externo verificado. También consulta segmentos de origen cuando no puede probarse la identidad del episodio. Para usar IDs externos coloque `mappings.db` junto a la base de tiempos.

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

## Recopilación API e importación

Dos recolectores consultan AniSkip v2 (MAL/episodio) y Anime Skip GraphQL (AniList/episodios). Admiten límites, checkpoints y reanudación. Un episodio positivo no demuestra que se hayan revisado todos los posteriores.

Las ramas públicas `crawler-state-aniskip` y `crawler-state-anime_skip` guardan estado entre ejecuciones. Solo se importan snapshots cuando ambos puntos de control son válidos; se excluyen datos incompletos.

Anime Skip usa el secreto privado `ANIME_SKIP_CLIENT_ID`. El acceso a una API no concede derechos automáticos de redistribución. La importación local requiere `--api-checkpoint-dir` y la confirmación `--allow-api-redistribution` conforme a los avisos.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Bases de datos y versiones

Las compilaciones habituales publican artefactos de GitHub Actions; las versiones permanentes se publican mediante tags o ejecución manual. Incluyen `timestamps.db`, `timestamps-evidence.db`, copias comprimidas, `manifest.json`, `audit.json`, `SHA256SUMS` y avisos.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

El proyecto es independiente de **anime-db-bot** y no es una dependencia obligatoria. Compruebe el esquema, la cobertura y las condiciones de los datos antes de integrarlo o distribuirlo.

## Archivos distribuidos

Los builds normales generan artefactos temporales de Actions; tags y ejecuciones manuales publican Releases. Runtime y evidencia se entregan por separado. `manifest.json` detalla fuentes, huella de mappings, esquema y tamaños; `audit.json` resume comprobaciones.

| Tabla o archivo | Función |
| --- | --- |
| `timestamps.db` | SQLite runtime compacta |
| `timestamps-evidence.db` | SQLite de evidencias |
| `*.db.zst` | Distribuciones comprimidas |
| `manifest.json` | Fuentes, versiones, tamaños y hashes |
| `audit.json` | Informe de auditoría |
| `SHA256SUMS` | Sumas SHA-256 |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Avisos de licencia y atribución |

## Auditoría y reproducibilidad

Se revisan integridad SQLite, claves externas, intervalos válidos, referencias a títulos y episodios, miembros del consenso y cobertura real. Tanto las bases intermedias estrictas como las distribuciones compactas se auditan para evitar relaciones inválidas.

Se registran URLs, SHA-256, tamaños y metadatos de descarga. Se consume una versión validada de Anime Mapping DB localmente. Los conteos y tamaños vigentes deben consultarse en el manifest, no en cifras fijas del README.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Límites de integración

Es independiente de anime-db-bot y no es su dependencia obligatoria. Los builds normales no rastrean sitios de streaming, no garantizan datos para cada obra ni fuerzan uniones de episodios por aumentar cobertura.

## Documentación

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licencia y atribuciones

Código: Apache-2.0. Los datos compilados conservan los términos de datasets y API originales. Algunas fuentes tienen obligaciones especiales o carecen de licencia explícita; consulte los avisos. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
