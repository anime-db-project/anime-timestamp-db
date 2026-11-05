"""Update statistics in all localized READMEs from a published timestamp build.

The inputs must be the same release manifest and measured read-only runtime
benchmark. No queries to upstream timestamp APIs occur during this operation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

BEGIN = "<!-- BEGIN AUTO-GENERATED DATABASE STATS -->"
END = "<!-- END AUTO-GENERATED DATABASE STATS -->"
REPO = "anime-db-project/anime-timestamp-db"
LANGUAGES = ("en", "ru", "ja", "de", "es", "fr", "it")
WORDS: dict[str, dict[str, Any]] = {
    "en": {
        "title": "Database at a glance",
        "hero": "{episodes} normalized episodes · {segments} mapped intervals · {consensus} consensus intervals",
        "intro": "These are separate metrics and must not be added as unique anime or scenes. Source-only observations are accessible but are not counted as normalized episodes.",
        "metric": "Metric",
        "value": "Value",
        "labels": [
            "AMDB titles with timestamp data",
            "Normalized episodes",
            "Mapped source intervals",
            "Unresolved source-only intervals",
            "Consensus intervals",
            "Consensus evidence memberships",
            "Evidence records",
            "Input snapshots",
            "Runtime SQLite size",
            "Compressed SQLite size",
        ],
        "bench": "Local lookup performance",
        "speed": ["Median", "p95", "p99", "Sequential queries/s"],
        "source": "Source intervals",
        "cons": "Consensus intervals",
        "note": "Warm-cache sequential read-only queries on released SQLite, {environment}; {sampled} sampled episodes × {rounds} rounds. These are local lookup measurements, not network/API latency.",
        "build": "Source download and database build",
        "snapshot": "Release snapshot",
        "latest": "Current release manifest",
        "pending": "No measured local benchmark is available for this snapshot.",
    },
    "ru": {
        "title": "Статистика базы таймкодов",
        "hero": "{episodes} нормализованных серий · {segments} сопоставленных интервалов · {consensus} консенсусных интервалов",
        "intro": "Это разные показатели, их нельзя складывать как количество тайтлов или сцен. Интервалы без подтверждённого номера серии доступны по исходным ID, но не входят в число нормализованных эпизодов.",
        "metric": "Показатель",
        "value": "Значение",
        "labels": [
            "Тайтлы с таймкодами и AMDB ID",
            "Нормализованные серии",
            "Сопоставленные интервалы",
            "Source-only интервалы",
            "Консенсусные интервалы",
            "Связи консенсуса с evidence",
            "Записи evidence",
            "Снимки источников",
            "Размер SQLite",
            "Размер сжатой SQLite",
        ],
        "bench": "Скорость локального получения таймкодов",
        "speed": ["Медиана", "p95", "p99", "Последовательные запросы/с"],
        "source": "Исходные интервалы",
        "cons": "Консенсусные интервалы",
        "note": "Последовательные запросы к релизной SQLite с прогретым кэшем, {environment}; {sampled} серий × {rounds} повторения. Показатели не измеряют сетевую задержку API.",
        "build": "Загрузка источников и сборка БД",
        "snapshot": "Снимок релиза",
        "latest": "Актуальный манифест",
        "pending": "Для этого снимка нет измеренного benchmark.",
    },
    "ja": {
        "title": "データベースの収録状況",
        "hero": "正規化 {episodes}話 · 区間 {segments}件 · 合意区間 {consensus}件",
        "intro": "各値は別の指標で、作品や場面の合計にはできません。ソース固有の区間は検索できますが正規化話数には含みません。",
        "metric": "指標",
        "value": "値",
        "labels": [
            "タイムスタンプのある AMDB 作品",
            "正規化された話数",
            "正規化された区間",
            "ソース固有の未解決区間",
            "合意区間",
            "合意の根拠リンク",
            "証拠レコード",
            "元データスナップショット",
            "SQLite サイズ",
            "圧縮 SQLite サイズ",
        ],
        "bench": "ローカル検索性能",
        "speed": ["中央値", "p95", "p99", "逐次検索/秒"],
        "source": "元ソース区間",
        "cons": "合意区間",
        "note": "リリース SQLite へのキャッシュ済み逐次読み取り、{environment}。{sampled}話 × {rounds}回。ネットワーク API の遅延ではありません。",
        "build": "元データ取得と DB ビルド",
        "snapshot": "リリース時点",
        "latest": "最新マニフェスト",
        "pending": "このスナップショットの計測値はありません。",
    },
    "de": {
        "title": "Datenbank in Zahlen",
        "hero": "{episodes} normalisierte Folgen · {segments} zugeordnete Intervalle · {consensus} Konsensintervalle",
        "intro": "Dies sind separate Kennzahlen und keine addierbaren Titelzahlen. Quelleneigene Bereiche bleiben abrufbar, gelten aber nicht als normalisierte Episoden.",
        "metric": "Kennzahl",
        "value": "Wert",
        "labels": [
            "AMDB-Titel mit Zeitstempeln",
            "Normalisierte Folgen",
            "Zugeordnete Intervalle",
            "Quelleneigene Intervalle",
            "Konsensintervalle",
            "Konsensmitgliedschaften",
            "Evidenzrecords",
            "Quell-Snapshots",
            "SQLite-Größe",
            "Komprimierte SQLite-Größe",
        ],
        "bench": "Lokale Abfrageleistung",
        "speed": ["Median", "p95", "p99", "Sequentielle Abfragen/s"],
        "source": "Quellintervalle",
        "cons": "Konsensintervalle",
        "note": "Sequentielle Abfragen auf Release-SQLite mit warmem Cache, {environment}; {sampled} Folgen × {rounds} Runden. Keine API-/Netzwerklatenz.",
        "build": "Quellenbezug und DB-Aufbau",
        "snapshot": "Release-Snapshot",
        "latest": "Aktuelles Manifest",
        "pending": "Keine Messdaten für diesen Snapshot vorhanden.",
    },
    "es": {
        "title": "El dataset en cifras",
        "hero": "{episodes} episodios normalizados · {segments} intervalos · {consensus} consensos",
        "intro": "Son métricas diferentes y no deben sumarse como títulos o escenas. Los intervalos nativos sin resolver se pueden consultar, pero no cuentan como episodios normalizados.",
        "metric": "Indicador",
        "value": "Valor",
        "labels": [
            "Títulos AMDB con intervalos",
            "Episodios normalizados",
            "Intervalos asociados",
            "Intervalos nativos no resueltos",
            "Intervalos de consenso",
            "Relaciones de consenso",
            "Registros de evidencia",
            "Instantáneas de fuentes",
            "Tamaño SQLite",
            "SQLite comprimido",
        ],
        "bench": "Rendimiento de búsqueda local",
        "speed": ["Mediana", "p95", "p99", "Consultas secuenciales/s"],
        "source": "Intervalos de origen",
        "cons": "Intervalos de consenso",
        "note": "Consultas secuenciales con caché caliente sobre SQLite publicada, {environment}; {sampled} episodios × {rounds} rondas. No representan latencia de red/API.",
        "build": "Descarga de fuentes y generación",
        "snapshot": "Versión de referencia",
        "latest": "Manifiesto actual",
        "pending": "No hay resultados de benchmark para esta versión.",
    },
    "fr": {
        "title": "La base en chiffres",
        "hero": "{episodes} épisodes normalisés · {segments} intervalles · {consensus} consensus",
        "intro": "Ces nombres mesurent des choses différentes et ne se cumulent pas comme des titres. Les plages natives non résolues restent consultables mais ne sont pas comptées comme épisodes normalisés.",
        "metric": "Indicateur",
        "value": "Valeur",
        "labels": [
            "Titres AMDB avec intervalles",
            "Épisodes normalisés",
            "Intervalles associés",
            "Plages non résolues",
            "Intervalles de consensus",
            "Membres des consensus",
            "Enregistrements de preuves",
            "Snapshots de sources",
            "Taille SQLite",
            "SQLite compressée",
        ],
        "bench": "Performance des recherches locales",
        "speed": ["Médiane", "p95", "p99", "Requêtes séquentielles/s"],
        "source": "Intervalles sources",
        "cons": "Intervalles de consensus",
        "note": "Lectures séquentielles sur SQLite publiée avec cache chaud, {environment} ; {sampled} épisodes × {rounds} tours. Ce n'est pas la latence réseau/API.",
        "build": "Téléchargement et construction",
        "snapshot": "Instantané de version",
        "latest": "Manifeste actuel",
        "pending": "Aucun benchmark disponible pour cette version.",
    },
    "it": {
        "title": "Il database in numeri",
        "hero": "{episodes} episodi normalizzati · {segments} intervalli · {consensus} consensi",
        "intro": "Sono metriche diverse, da non sommare come titoli o scene. Gli intervalli nativi non risolti sono consultabili ma non contano come episodi normalizzati.",
        "metric": "Indicatore",
        "value": "Valore",
        "labels": [
            "Titoli AMDB con intervalli",
            "Episodi normalizzati",
            "Intervalli associati",
            "Intervalli nativi non risolti",
            "Intervalli di consenso",
            "Collegamenti del consenso",
            "Record di prova",
            "Snapshot delle fonti",
            "Dimensione SQLite",
            "SQLite compresso",
        ],
        "bench": "Prestazioni delle query locali",
        "speed": ["Mediana", "p95", "p99", "Query sequenziali/s"],
        "source": "Intervalli delle fonti",
        "cons": "Intervalli di consenso",
        "note": "Query sequenziali con cache calda sulla SQLite pubblicata, {environment}; {sampled} episodi × {rounds} round. Non misura la latenza API.",
        "build": "Download sorgenti e build DB",
        "snapshot": "Snapshot della release",
        "latest": "Manifest attuale",
        "pending": "Nessun benchmark disponibile per questa versione.",
    },
}


def formatted(value: int) -> str:
    return f"{value:,}"


def size_mib(value: int) -> str:
    return f"{value / (1024 * 1024):,.1f} MiB"


def render_stats(
    manifest: dict[str, Any], performance: dict[str, Any] | None, locale: str, tag: str
) -> str:
    if not re.fullmatch(r"v[A-Za-z0-9_.-]+", tag):
        raise ValueError(f"Invalid release tag: {tag!r}")
    t = WORDS[locale]
    audit = manifest["audit"]
    if not audit["ok"]:
        raise ValueError("Cannot publish statistics from an unsuccessful audit")
    runtime = audit["runtime"]["counts"]
    evidence = audit["evidence"]["counts"]
    artifacts = manifest["artifacts"]
    main_values = [
        runtime["titles"],
        runtime["episodes"],
        runtime["segments"],
        runtime["source_segments"],
        runtime["consensus_segments"],
        runtime["consensus_members"],
        evidence["records"],
        evidence["source_snapshots"],
    ]
    values = [formatted(int(v)) for v in main_values] + [
        size_mib(int(artifacts["timestamps.db"]["size_bytes"])),
        size_mib(int(artifacts["timestamps.db.zst"]["size_bytes"])),
    ]
    lines = [
        BEGIN,
        f"## {t['title']}",
        "",
        f"**{t['hero'].format(episodes=formatted(runtime['episodes']), segments=formatted(runtime['segments']), consensus=formatted(runtime['consensus_segments']))}**",
        "",
        t["intro"],
        "",
        f"| {t['metric']} | {t['value']} |",
        "| --- | ---: |",
    ]
    lines.extend(
        f"| {label} | **{value}** |"
        for label, value in zip(t["labels"], values, strict=True)
    )
    lines.extend(["", f"### {t['bench']}", ""])
    if performance is None:
        lines.append(str(t["pending"]))
    else:
        if int(performance["database_bytes"]) != int(
            artifacts["timestamps.db"]["size_bytes"]
        ):
            raise ValueError("Benchmark SQLite size differs from release runtime asset")
        for key, title in (
            ("normalized_lookup", t["source"]),
            ("consensus_lookup", t["cons"]),
        ):
            values = performance[key]
            labels = t["speed"]
            results = [
                f"{float(values[k]):.3f} ms" for k in ("median_ms", "p95_ms", "p99_ms")
            ] + [formatted(round(float(values["lookups_per_second"])))]
            lines.extend(
                [
                    f"**{title}**",
                    "",
                    f"| {t['metric']} | {t['value']} |",
                    "| --- | ---: |",
                ]
            )
            lines.extend(
                f"| {name} | **{value}** |"
                for name, value in zip(labels, results, strict=True)
            )
            lines.append("")
        build = performance.get("build_seconds")
        if build is not None:
            lines.append(f"{t['build']}: **{int(build):,} s**.")
            lines.append("")
        lines.append(
            t["note"].format(
                environment=performance.get("environment", "Linux / CPython"),
                sampled=performance["sampled_episodes"],
                rounds=performance["rounds"],
            )
        )
    date = str(manifest["generated_at"]).split("T")[0]
    lines.extend(
        [
            "",
            f"{t['snapshot']}: **{date}**, [{tag}](https://github.com/{REPO}/releases/tag/{tag}). "
            f"[{t['latest']}](https://github.com/{REPO}/releases/latest/download/manifest.json).",
            "",
            END,
            "",
        ]
    )
    return "\n".join(lines)


def update_readmes(
    root: Path,
    manifest: dict[str, Any],
    performance: dict[str, Any] | None,
    tag: str,
    *,
    check: bool = False,
) -> list[str]:
    replacements: list[tuple[Path, str]] = []
    changed: list[str] = []
    for locale in LANGUAGES:
        path = root / ("README.md" if locale == "en" else f"docs/README.{locale}.md")
        current = path.read_text(encoding="utf-8")
        section = render_stats(manifest, performance, locale, tag)
        if BEGIN in current or END in current:
            if current.count(BEGIN) != 1 or current.count(END) != 1:
                raise ValueError(f"Corrupt generated section markers: {path}")
            start = current.index(BEGIN)
            finish = current.index(END, start) + len(END)
            updated = current[:start] + section.rstrip("\n") + current[finish:]
        else:
            heading = str(WORDS[locale]["title"])
            pattern = re.compile(
                rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)", re.M | re.S
            )
            if len(pattern.findall(current)) != 1:
                raise ValueError(f"Could not locate one statistics block: {path}")
            updated = pattern.sub(lambda _: section + "\n", current, count=1)
        replacements.append((path, updated))
        if updated != current:
            changed.append(str(path.relative_to(root)))
    if not check:
        for path, updated in replacements:
            if path.read_text(encoding="utf-8") != updated:
                path.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    p = argparse.ArgumentParser(
        description="Refresh timestamp statistics in seven README translations"
    )
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--performance", type=Path)
    p.add_argument("--tag", required=True, help="The tag of the just-published release")
    p.add_argument("--root", type=Path, default=Path("."))
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    performance = (
        json.loads(a.performance.read_text(encoding="utf-8")) if a.performance else None
    )
    changed = update_readmes(a.root, manifest, performance, a.tag, check=a.check)
    print(
        f"README statistics: {len(changed)} changes ({', '.join(changed) or 'up to date'})"
    )
    return 1 if a.check and changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
