> **Проект разработан при помощи AI.**

<p align="center">
  <a href="../README.md">English</a> · <strong>Русский</strong> · <a href="README.ja.md">日本語</a> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

Самостоятельный инструмент и база SQLite с интервалами пропуска в сериях аниме: опенинги, эндинги, рекапы, превью и другие сегменты, с проверяемым происхождением записей.

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## Статистика базы таймкодов

**57,623 нормализованных серий · 214,241 сопоставленных интервалов · 125,085 консенсусных интервалов**

Это разные показатели, их нельзя складывать как количество тайтлов или сцен. Интервалы без подтверждённого номера серии доступны по исходным ID, но не входят в число нормализованных эпизодов.

| Показатель | Значение |
| --- | ---: |
| Тайтлы с таймкодами и AMDB ID | **4,340** |
| Нормализованные серии | **57,623** |
| Сопоставленные интервалы | **214,241** |
| Source-only интервалы | **44,646** |
| Консенсусные интервалы | **125,085** |
| Связи консенсуса с evidence | **184,429** |
| Записи evidence | **299,537** |
| Снимки источников | **8** |
| Размер SQLite | **52.5 MiB** |
| Размер сжатой SQLite | **14.1 MiB** |

### Скорость локального получения таймкодов

**Исходные интервалы**

| Показатель | Значение |
| --- | ---: |
| Медиана | **0.853 ms** |
| p95 | **1.099 ms** |
| p99 | **1.146 ms** |
| Последовательные запросы/с | **1,167** |

**Консенсусные интервалы**

| Показатель | Значение |
| --- | ---: |
| Медиана | **0.627 ms** |
| p95 | **0.874 ms** |
| p99 | **0.948 ms** |
| Последовательные запросы/с | **1,510** |

Последовательные запросы к релизной SQLite с прогретым кэшем, Linux / Python 3.12; 180 серий × 2 повторения. Показатели не измеряют сетевую задержку API.

Снимок релиза: **2026-11-05**, [v2026.11.05.8](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.05.8). [Актуальный манифест](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

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

## Варианты использования базы таймкодов

Готовый SQLite можно использовать без запуска сборщиков API, без ключей и без пересборки проекта. В зависимости от задачи доступны следующие варианты:

- **Видеоплееры.** Добавляйте кнопки пропуска OP, ED, рекапа и превью при наличии данных для конкретной серии.
- **Аниме-каталоги и сайты.** Показывайте разметку таймлайна серии, происхождение интервалов и согласованность источников.
- **Боты и приложения.** Находите тайтл по AMDB либо проверенному ID MAL/AniList/AniDB и возвращайте интервалы нужного источника или консенсус.
- **Офлайн- и мобильные приложения.** Поставляйте SQLite вместе с приложением для локального чтения без запросов к API в runtime.
- **Аудит и анализ.** Сравнивайте исходные наблюдения и консенсус, находите source-only записи и изучайте доказательства.

Скачайте опубликованные базы. Если приложение работает только с AMDB ID, достаточно `timestamps.db`. Для поиска по внешним ID MAL/AniList и другим потребуется также совместимая `mappings.db`:

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

Используйте `TimestampResolver` из Python-пакета (`python -m pip install -e .` в клоне timestamp-репозитория). Исходные интервалы и консенсус можно получать независимо:

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

Прямое чтение SQLite возможно на любом языке с драйвером SQLite. Пример SQL для нормализованных интервалов по AMDB ID и ключу серии:

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

Замените примерный AMDB ID и номер серии на существующие в вашей версии базы. `start_ms` и `end_ms` хранятся **в целых миллисекундах** — для плеера, работающего в секундах, делите на 1000. Наличие тайтла в Anime Mapping DB не гарантирует наличия таймкодов.

Неразрешённые записи доступны через `source-lookup` или `source-anchor`. Собственный ключ серии источника нельзя автоматически считать номером серии MAL/AniList.

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

При совместном использовании сверяйте версии, SHA-256 и манифесты. Релиз таймкодов фиксирует точный хеш использованной mapping-базы; несовместимые снимки могут привести к пропущенным совпадениям или редиректам anchor.

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

Постоянные файлы баз публикуются в GitHub Releases по тегам или вручную. Релиз содержит `timestamps.db`, `timestamps-evidence.db`, сжатые версии, `manifest.json`, `audit.json`, `performance.json`, `SHA256SUMS` и уведомления об источниках.

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

Проект независим от **anime-db-bot** и не является обязательной зависимостью бота. Перед интеграцией или распространением учитывайте покрытие источников, схему и условия использования данных.

## Файлы сборок и релизов

Для скачивания используйте GitHub Releases. Компактная runtime-база распространяется отдельно от evidence. `manifest.json` содержит исходные версии, fingerprint mappings.db, схему и размеры; `audit.json` — проверки, а `performance.json` — замеры скорости локальных запросов.

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
