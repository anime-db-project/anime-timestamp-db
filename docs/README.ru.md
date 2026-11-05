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

## Покрытие и нормализация источников

Источники таймкодов различаются системой ID, нумерацией серий и полнотой покрытия. Корректный интервал ещё не доказывает, что перед нами та же серия в MAL или AniList. Сборщик разделяет нормализованные, доступные по исходному ID и отклонённые данные, вместо того чтобы создавать ложные соответствия.

- AniSkip public: интервалы по ID MyAnimeList и номеру серии; в нормализованную базу попадают только подтверждённые AMDB anchors.
- SkipDB: таймкоды с привязкой к IMDb; AniBridge и Anime Mapping DB должны подтвердить конкретную серию аниме.
- Open Anime Timestamps: записи AniDB; агрегированные источники сохраняются, но не создают дополнительных независимых голосов консенсуса.
- Baha Anime Skip: серии по собственным ключам `videoSn`; данные остаются доступными по ним без выдумывания ID MAL/AniList.
- API AniSkip и Anime Skip: сохранённые контрольные точки могут дополнять открытые файлы после проверки и учёта прав.

## Идентификаторы тайтлов и серий

Идентичность тайтлов предоставляет Anime Mapping DB. Нормализованный тайтл использует `anchor_id`, публично — `amdb:<anchor_id>`. База таймкодов не дублирует весь граф ID и внешние aliases. Для поиска по `mal`, `anilist`, `anidb` и другим ID приложение подключает отдельную `mappings.db`.

Идентичность серии строже идентичности тайтла. Разные платформы могут назвать «серией 1» разные единицы воспроизведения: провайдер, scope и номер требуют независимого подтверждения. Дробные номера вроде 12.5, спецвыпуски и фильмы не округляются и не объединяются наугад. Пропорциональные сопоставления AniBridge для разделённых/объединённых серий не уплощаются.

Если можно доказать тайтл, но нельзя сопоставить серию, запись связывается с AMDB через `source_title_refs`, а интервалы остаются в `source_segments`. Так данные можно найти без ошибочного канонического номера серии.

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

## Схема runtime- и evidence-баз

Компактная `timestamps.db` предназначена для приложений. Таблица `titles` содержит стабильные AMDB anchors, `episodes` — нормализованные единицы воспроизведения, `episode_ids` — подтверждённую нумерацию по провайдерам, `episode_refs` — оригинальные ссылки на серии, `segments` — сопоставленные интервалы.

`source_segments` сохраняет корректные, но неоднозначные диапазоны. `source_title_refs` содержит лишь проверенные собственные ключи тайтлов, а не все ID MAL/AniList. `consensus_segments` и `consensus_members` фиксируют итоговые интервалы и точный состав наблюдений. `sources` и `lineages` различают источник данных и независимое происхождение.

| Таблица или файл | Назначение |
| --- | --- |
| `titles` | Стабильный AMDB ID тайтла |
| `episodes` | Подтверждённая единица воспроизведения |
| `episode_ids` | Номера серий отдельных провайдеров |
| `episode_refs` | Исходные ключи серий источников |
| `segments` | Нормализованные интервалы |
| `source_segments` | Диапазоны без подтверждённой связи |
| `sources / lineages` | Источники и независимые цепочки происхождения |
| `consensus_segments / consensus_members` | Консенсус и его участники |
| `timestamps-evidence.db` | Сведения об исходных данных и решениях |

`timestamps-evidence.db` хранит снимки исходных файлов, хеши, решения нормализации и первоначальные интервалы. Она нужна для аудита и атрибуции, а не для обычного воспроизведения. Временные границы в базе хранятся целыми миллисекундами.

## Консенсус и происхождение данных

Консенсус вычисляется отдельно от исходных записей. Взвешенная медиана группирует совместимые интервалы с заданной погрешностью, учитывает достоверность сопоставления и не считает зеркала одного источника несколькими голосами. Неподходящие или агрегированные записи сохраняются, но не голосуют.

Стандартный допуск границ — 5 секунд; его можно изменить через `--consensus-tolerance-ms`. Итоговый диапазон — производный вариант, а не гарантия совпадения времени во всех изданиях. Для точного воспроизведения учитывайте исходные наблюдения.

## Быстрый старт

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## Командная строка

CLI создаёт пустую схему, собирает данные, показывает состояние баз, проводит аудит, ищет нормализованные и исходные записи. `lookup` принимает `--episode` либо `--episode-key`, умеет фильтровать источник и показывать consensus. Для ID вне `amdb` подключайте совместимую `mappings.db`.

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
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

## Интеграция через Python

`TimestampResolver` выдаёт исходные интервалы и консенсус по AMDB anchor либо проверенному внешнему ID. Также можно получать записи по собственным ID источника, когда нумерацию серий нельзя безопасно объединить. Для запросов по внешним ID держите `mappings.db` рядом с базой таймкодов.

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

## API-сборщики и импорт в релизы

Два независимых сборщика используют AniSkip v2 (MAL/серия) и Anime Skip GraphQL (AniList/серии). Запросы ограничены, состояние сохраняется и работа возобновляется после перерыва. Наличие ответа для ранней серии не доказывает, что все последующие серии уже проверены.

Публичные ветки `crawler-state-aniskip` и `crawler-state-anime_skip` сохраняют контрольные точки между запусками Actions. Импорт в сборки/релизы выполняется только при наличии обеих валидных контрольных точек. Частичные и повреждённые снимки не смешиваются с релизной базой.

Для Anime Skip используется приватный секрет `ANIME_SKIP_CLIENT_ID`. Доступность API сама по себе не даёт права на дальнейшее распространение данных. Локальный импорт требует `--api-checkpoint-dir` и явного подтверждения `--allow-api-redistribution`; учитывайте лицензии источников.

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## Базы данных и релизы

Обычные сборки публикуют артефакты GitHub Actions; релизы создаются по тегу или вручную. Пакет содержит `timestamps.db`, `timestamps-evidence.db`, сжатые копии, `manifest.json`, `audit.json`, `SHA256SUMS` и обязательные уведомления.

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Проект независим от **anime-db-bot** и не является обязательной зависимостью бота. Перед интеграцией или распространением учитывайте покрытие источников, схему и условия использования данных.

## Файлы сборок и релизов

Обычные сборки публикуют временные артефакты GitHub Actions; релизы по тегу и ручному запуску остаются в GitHub Releases. Runtime-база компактна, evidence хранится отдельно. `manifest.json` описывает входные данные, fingerprint mappings.db, схему, размер и сборку; `audit.json` — результаты проверок.

| Таблица или файл | Назначение |
| --- | --- |
| `timestamps.db` | Компактная runtime SQLite |
| `timestamps-evidence.db` | База происхождения и доказательств |
| `*.db.zst` | Сжатые версии баз |
| `manifest.json` | Версии, источники, размеры и хеши |
| `audit.json` | Результаты аудита |
| `SHA256SUMS` | Контрольные суммы SHA-256 |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | Уведомления об авторстве и лицензиях |

## Аудит и воспроизводимость

Каждая сборка проверяется на целостность и внешние ключи SQLite, корректность интервалов, ссылки на тайтлы и серии, состав консенсуса и наличие реальных данных. Проверяются строгие промежуточные и компактные выходные базы. Отвергнутые соответствия не должны проникать в нормализованные записи.

Для исходных снимков сохраняются URL, SHA-256, объём и метаданные загрузки. Сборщик локально использует проверенную фиксированную версию Anime Mapping DB. Актуальные цифры покрытия и размера берите из manifest, а не из устаревающих чисел README.

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## Границы применения

Проект самостоятельный и не является обязательной частью anime-db-bot. Обычная сборка не обходит стриминговые сайты, не гарантирует наличие таймкодов для каждого тайтла и не объединяет сомнительные сезоны/серии ради увеличения покрытия.

## Документация

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## Лицензия и атрибуция

Код — Apache-2.0. На данные распространяются условия исходных наборов и API. Для отдельных источников действуют особые требования атрибуции либо отсутствует явно опубликованная лицензия; читайте уведомления. [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
