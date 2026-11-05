> **Проект разработан при помощи AI.**

<p align="center">
  <a href="../README.md">English</a> · <strong>Русский</strong> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Самостоятельный инструмент и база SQLite с интервалами пропуска в сериях аниме: опенинги, эндинги, рекапы, превью и другие сегменты, с проверяемым происхождением записей.

## Возможности

- Привязка таймкодов к тайтлам и сериям через проверенные идентификаторы Anime Mapping DB.
- Сохранение корректных, но не сопоставленных записей под ID исходного сервиса.
- Расчёт консенсуса по независимым наблюдениям без повторного учёта зеркал.
- Отдельные компактная runtime-база, доказательства, аудит и контрольные суммы.
- Импорт статических баз и возобновляемые сборщики API AniSkip / Anime Skip.

## Источники данных

Обычные сборки используют открытые файлы источников и снимок Anime Mapping DB. Два API-сборщика сохраняют контрольные точки; проверенные снимки могут импортироваться при сборке и выпуске. Работа API и необходимые учётные данные описаны отдельно.

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — Интервалы из открытого набора с идентификаторами MAL
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — Данные пропуска серий, связанные с IMDb
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — Таймкоды AniDB и агрегированные записи
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Исходные интервалы по сериям Bahamut
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — Сопоставление идентификаторов и нумерации серий
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — Стабильные идентификаторы аниме
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — API-сбор данных с контрольными точками

Нормализованные записи используют общий ID `amdb:<anchor_id>`. Номера серий между сервисами связываются только при проверенных соответствиях; спорные данные остаются доступными в исходном виде. [Контракт схемы](../docs/SCHEMA.md).

## Быстрый старт

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Использование

```bash
# Поиск по стабильному идентификатору аниме
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# Для внешнего ID передайте базу сопоставлений
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# Исходные интервалы без подтверждённого межбазового соответствия
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## Базы данных и релизы

Обычные сборки публикуют артефакты GitHub Actions; релизы создаются по тегу или вручную. Пакет содержит `timestamps.db`, `timestamps-evidence.db`, сжатые копии, `manifest.json`, `audit.json`, `SHA256SUMS` и обязательные уведомления.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Проект независим от **anime-db-bot** и не является обязательной зависимостью бота. Перед интеграцией или распространением учитывайте покрытие источников, схему и условия использования данных.

## Документация

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Лицензия и атрибуция

Код — Apache-2.0. На данные распространяются условия исходных наборов и API. Для отдельных источников действуют особые требования атрибуции либо отсутствует явно опубликованная лицензия; читайте уведомления. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
