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

## Inicio rápido

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
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

## Bases de datos y versiones

Las compilaciones habituales publican artefactos de GitHub Actions; las versiones permanentes se publican mediante tags o ejecución manual. Incluyen `timestamps.db`, `timestamps-evidence.db`, copias comprimidas, `manifest.json`, `audit.json`, `SHA256SUMS` y avisos.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

El proyecto es independiente de **anime-db-bot** y no es una dependencia obligatoria. Compruebe el esquema, la cobertura y las condiciones de los datos antes de integrarlo o distribuirlo.

## Documentación

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Licencia y atribuciones

Código: Apache-2.0. Los datos compilados conservan los términos de datasets y API originales. Algunas fuentes tienen obligaciones especiales o carecen de licencia explícita; consulte los avisos. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
