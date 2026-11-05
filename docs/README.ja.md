> **AI 支援プロジェクト:** AI の支援を受けて開発されています。

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <strong>日本語</strong> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Database build](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

アニメの OP、ED、回想、予告などのスキップ区間を、出典を追跡できる SQLite データとして構築する独立したプロジェクトです。

## 主な機能

- Anime Mapping DB の検証済み ID に基づく作品・エピソードへの紐付け。
- 紐付け不能でも有効な記録はソース固有 ID で参照可能。
- ミラーを独立した票として数えず、証拠付きの合意区間を算出。
- 実行用 DB、証拠 DB、監査結果、チェックサムを分けて配布。
- 公開データの取り込みと AniSkip / Anime Skip API の再開可能な収集。

## データソース

通常のビルドは公開バルクデータと Anime Mapping DB を使用します。二つの API コレクターはチェックポイントを保存し、検証済みのスナップショットをビルドに取り込めます。詳細は専用ドキュメントを参照してください。

- [AniSkip dataset](https://github.com/aniskip/sanitize-db-dump) — MAL ID に基づく公開タイムスタンプデータ
- [SkipDB](https://github.com/SkipDB-TV/skipdb) — IMDb に紐付くエピソードのスキップ情報
- [Open Anime Timestamps](https://github.com/Ellivers/open-anime-timestamps) — AniDB タイムスタンプと集約記録
- [Baha Anime Skip](https://github.com/JacobLinCool/baha-anime-skip) — Bahamut 固有のエピソード区間
- [AniBridge](https://github.com/anibridge/anibridge-mappings) — エピソード ID と番号体系の橋渡し
- [Anime Mapping DB](https://github.com/anime-db-project/anime-mapping-db) — 安定したアニメ作品 ID
- [AniSkip API](https://api.aniskip.com/) / [Anime Skip API](https://anime-skip.com/) — チェックポイント付き API データ収集

正規化されたタイトル ID は `amdb:<anchor_id>` です。異なるサービスのエピソード番号は明示的に確認できる場合のみ対応付け、曖昧な記録は元のソース形式で保持します。 [スキーマ仕様](../docs/SCHEMA.md).

## クイックスタート

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## 使い方

```bash
# プロジェクトの安定したアニメ ID で検索
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1

# 外部 ID にはマッピング DB を指定
anime-timestamp-db lookup --db artifacts/timestamps.db --mapping-db mappings.db --provider mal --id 5114 --episode 1

# 対応関係が未確定なソース固有の区間
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
```

## データベースとリリース

通常のビルドは GitHub Actions のアーティファクトを公開します。タグまたは手動操作で Releases を発行します。`timestamps.db`、`timestamps-evidence.db`、圧縮版、`manifest.json`、`audit.json`、`SHA256SUMS`、通知ファイルを含みます。

- [Database build artifacts](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/build.yml)
- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

このプロジェクトは **anime-db-bot** とは独立しており、ボットの必須依存ではありません。統合・再配布前にスキーマ、収録範囲、元データの規約を確認してください。

## ドキュメント

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## ライセンスと出典

コードは Apache-2.0 です。生成データには元データセットと API の規約が適用されます。明示的なデータライセンスがないソースもあるため、再配布前に通知文書を確認してください。 [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
