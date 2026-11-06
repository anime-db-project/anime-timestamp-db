> **AI 支援プロジェクト:** AI の支援を受けて開発されています。

<p align="center">
  <a href="../README.md">English</a> · <a href="README.ru.md">Русский</a> · <strong>日本語</strong> · <a href="README.de.md">Deutsch</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.it.md">Italiano</a>
</p>

# anime-timestamp-db

[![CI](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/ci.yml)
[![Releases](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml/badge.svg)](https://github.com/anime-db-project/anime-timestamp-db/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/Python-3.11--3.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Code license](https://img.shields.io/badge/Code-Apache%202.0-D22128.svg)](../LICENSE)
[![Data license](https://img.shields.io/badge/Data-ODbL%201.0%20%2B%20upstream%20terms-555555.svg)](../DATA_LICENSE.md)

アニメの OP、ED、回想、予告などのスキップ区間を、出典を追跡できる SQLite データとして構築する独立したプロジェクトです。

<!-- BEGIN AUTO-GENERATED DATABASE STATS -->
## データベースの収録状況

**正規化 58,008話 · 区間 227,033件 · 合意区間 130,970件**

各値は別の指標で、作品や場面の合計にはできません。ソース固有の区間は検索できますが正規化話数には含みません。

| 指標 | 値 |
| --- | ---: |
| タイムスタンプのある AMDB 作品 | **4,502** |
| 正規化された話数 | **58,008** |
| 正規化された区間 | **227,033** |
| ソース固有の未解決区間 | **65,432** |
| 合意区間 | **130,970** |
| 合意の根拠リンク | **197,113** |
| 証拠レコード | **333,836** |
| 元データスナップショット | **8** |
| SQLite サイズ | **60.1 MiB** |
| 圧縮 SQLite サイズ | **15.6 MiB** |

### ローカル検索性能

**元ソース区間**

| 指標 | 値 |
| --- | ---: |
| 中央値 | **0.363 ms** |
| p95 | **0.407 ms** |
| p99 | **0.445 ms** |
| 逐次検索/秒 | **2,704** |

**合意区間**

| 指標 | 値 |
| --- | ---: |
| 中央値 | **0.336 ms** |
| p95 | **0.357 ms** |
| p99 | **0.390 ms** |
| 逐次検索/秒 | **2,948** |

リリース SQLite へのキャッシュ済み逐次読み取り、Linux / Python 3.12。250話 × 2回。ネットワーク API の遅延ではありません。

リリース時点: **2026-11-06**, [v2026.11.06.18](https://github.com/anime-db-project/anime-timestamp-db/releases/tag/v2026.11.06.18). [最新マニフェスト](https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/manifest.json).

<!-- END AUTO-GENERATED DATABASE STATS -->

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

## 収録範囲と正規化

タイムスタンプソースごとに作品 ID、話数、収録範囲は異なります。ある区間が正しいことは、MAL と AniList の同一話を証明しません。ビルダーは確認済み、ソース専用、拒否済みの観測を分け、推測で対応関係を作りません。

- AniSkip 公開データ：MAL 作品 ID と話数を使い、確認済み AMDB anchor だけを正規化します。
- SkipDB：IMDb に結び付く区間を、AniBridge と Anime Mapping DB で特定の再生単位に照合します。
- Open Anime Timestamps：AniDB の観測と集約データを保存し、集約の重複票は認めません。
- Baha Anime Skip：Bahamut 固有の `videoSn` を保持し、MAL/AniList の話数を作りません。
- AniSkip / Anime Skip API：検証済みで利用条件を確認したチェックポイントを追加データとして利用できます。

## 作品・エピソードの ID

作品 ID の基準は Anime Mapping DB です。正規化されたタイトルは `anchor_id` で保存し、外部表記は `amdb:<anchor_id>` です。タイムスタンプ DB に外部タイトル ID の全対応表は複製しません。`mal`、`anilist`、`anidb` などで調べる場合は別の `mappings.db` を使用します。

作品が同じでも話数が同じとは限りません。プロバイダー、scope、話数の対応を個別に証明します。12.5 などの小数話、特別編、映画は安易に丸めたり統合したりしません。AniBridge の分割・結合比率も無理に 1:1 にしません。

作品が確認できても話数が不明なら、`source_title_refs` から AMDB anchor を参照し、区間は `source_segments` に保持します。誤った正規化なしで検索できるようにするためです。

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

## 実行用・証拠用スキーマ

軽量な `timestamps.db` はアプリ向けです。`titles` は AMDB 作品 ID、`episodes` は正規化された再生単位、`episode_ids` は確認済みの話数、`episode_refs` は元ソースの話参照、`segments` は正規化された区間を保存します。

`source_segments` は未解決の有効区間を持ちます。`source_title_refs` は独立して検証された元ソースの作品キーのみを保持します。`consensus_segments` と `consensus_members` は合意区間と構成記録を示し、`sources` と `lineages` はデータセットと独立した出典を区別します。

| テーブルまたはファイル | 役割 |
| --- | --- |
| `titles` | 安定した AMDB 作品 ID |
| `episodes` | 検証済み再生単位 |
| `episode_ids` | サービス別の話数 |
| `episode_refs` | 元ソースの話キー |
| `segments` | 正規化された区間 |
| `source_segments` | 照合未完了の区間 |
| `sources / lineages` | ソースと独立した系統 |
| `consensus_segments / consensus_members` | 合意区間と構成観測 |
| `timestamps-evidence.db` | ビルドの出典と判断 |

`timestamps-evidence.db` は元ファイルのスナップショット、ハッシュ、変換の判断、元の区間を記録します。再現性や出典確認向けであり、通常の再生クエリは実行用 DB を使います。時間は整数ミリ秒です。

## 合意区間と出典

元観測は上書きせず、加重中央値で合意区間を別に生成します。許容誤差、照合の確からしさ、独立した系統を考慮し、ミラーを複数票としません。投票対象外でも元観測は検索可能です。

標準の境界許容誤差は 5 秒で、`--consensus-tolerance-ms` により変更できます。合意区間は推定値であり、配信版の編集差を保証しません。厳密な用途では元観測も確認してください。

## クイックスタート

Python 3.11+:

```bash
git clone https://github.com/anime-db-project/anime-timestamp-db.git
cd anime-timestamp-db
python -m pip install -e .
anime-timestamp-db build --output-dir artifacts
anime-timestamp-db audit --db artifacts/timestamps.db --evidence-db artifacts/timestamps-evidence.db
```

## コマンドライン

CLI はスキーマ作成、収集、検査、監査、正規化検索とソース固有検索を提供します。`lookup` には `--episode` または `--episode-key` が必要で、ソース指定や合意区間検索も可能です。外部作品 ID には `mappings.db` を接続します。

```bash
anime-timestamp-db schema-version
anime-timestamp-db inspect --db artifacts/timestamps.db
anime-timestamp-db lookup --db artifacts/timestamps.db --provider amdb --id 18472 --episode 1 --consensus
anime-timestamp-db source-anchor --db artifacts/timestamps.db --anchor amdb:18472 --title-refs
anime-timestamp-db source-lookup --db artifacts/timestamps.db --source baha --episode-key 123456
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

## Python での利用

`TimestampResolver` は AMDB anchor や確認済みの外部 ID から区間と合意結果を取得できます。また、正規化できないソース固有データも検索できます。外部 ID を使うアプリでは mapping DB も配置してください。

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

## データベースを利用する方法

配布 SQLite は API キーやクローラー、ビルド処理なしで使えます。主な利用例は次のとおりです。

- **動画プレーヤー.** データがある話に OP/ED、回想、予告のスキップ操作を追加します。
- **作品サイト.** 各話のタイムライン、元ソース、合意状況を表示します。
- **ボット・アプリ.** AMDB または検証済み MAL/AniList/AniDB ID で区間を取得します。
- **オフラインアプリ.** SQLite を同梱し、実行時に外部 API を呼ばずに検索します。
- **監査と分析.** 元データ、未解決区間、合意結果を比較します。

配布済み SQLite を取得します。AMDB ID だけなら `timestamps.db` で十分です。外部タイトル ID を使う場合は互換の `mappings.db` も必要です。

```bash
curl -fL -o timestamps.db \
  https://github.com/anime-db-project/anime-timestamp-db/releases/latest/download/timestamps.db
curl -fL -o mappings.db \
  https://github.com/anime-db-project/anime-mapping-db/releases/latest/download/mappings.db
```

リポジトリを `python -m pip install -e .` でインストールし、`TimestampResolver` から元区間と合意区間を取得します。

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

標準の SQLite ドライバーを使って直接参照することもできます。次は AMDB ID と話キーによる正規化区間の例です。

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

例の ID と話キーは実在する値に置き換えてください。`start_ms`、`end_ms` は**ミリ秒の整数**であり、秒を要求するプレーヤーでは 1000 で割ります。Mapping DB に作品があっても区間があるとは限りません。

未解決データは `source-lookup` または `source-anchor` で取得できます。ソースの話キーを MAL/AniList の話数と無条件にみなしてはいけません。

```bash
anime-timestamp-db source-anchor --db timestamps.db --anchor amdb:18472
anime-timestamp-db source-lookup --db timestamps.db --source baha --episode-key 123456
```

両方の DB を使う場合は互換のスナップショットとチェックサムを確認してください。タイムスタンプ側のマニフェストにはビルドに使用した Mapping DB のハッシュがあります。

## API 収集とリリース取り込み

AniSkip v2（MAL/話数）と Anime Skip GraphQL（AniList/エピソード）を別々に収集します。速度制限とチェックポイントによる再開に対応します。初期話数で結果があっても、後続話をすべて検索済みとはみなしません。

公開ブランチ `crawler-state-aniskip` と `crawler-state-anime_skip` に収集状態を保存します。両方のチェックポイントが有効な場合だけビルドやリリースに取り込み、不完全な状態を混ぜません。

Anime Skip には秘密の `ANIME_SKIP_CLIENT_ID` が必要です。API が使えることと再配布権は別です。ローカル取り込みでは `--api-checkpoint-dir` と `--allow-api-redistribution` による明示確認が必要です。

```bash
anime-timestamp-db build \
  --output-dir artifacts \
  --api-checkpoint-dir checkpoints \
  --allow-api-redistribution
```

## データベースとリリース

配布ファイルはタグまたは手動リリースによる GitHub Releases に公開します。`timestamps.db`、`timestamps-evidence.db`、圧縮版、`manifest.json`、`audit.json`、`performance.json`、`SHA256SUMS`、出典通知を含みます。

- [Releases](https://github.com/anime-db-project/anime-timestamp-db/releases)

このプロジェクトは **anime-db-bot** とは独立しており、ボットの必須依存ではありません。統合・再配布前にスキーマ、収録範囲、元データの規約を確認してください。

## 配布ファイル

配布には GitHub Releases を利用してください。実行用 SQLite と証拠データは分離されます。`manifest.json` に元データ、マッピングの指紋、スキーマ、サイズを記録し、`audit.json` に検証、`performance.json` にローカル検索の測定結果を保存します。

| テーブルまたはファイル | 役割 |
| --- | --- |
| `timestamps.db` | 軽量な実行用 SQLite |
| `timestamps-evidence.db` | 詳細な証拠 SQLite |
| `*.db.zst` | 圧縮配布版 |
| `manifest.json` | 入力、スキーマ、サイズ、ハッシュ |
| `audit.json` | 監査結果 |
| `SHA256SUMS` | SHA-256 チェックサム |
| `DATA_LICENSE.md / THIRD_PARTY_NOTICES.md` | ライセンス・出典通知 |

## 監査と再現性

SQLite の整合性、外部キー、有効な時間範囲、作品と話数のリンク、合意区間の構成、実データの存在を検証します。厳格な中間 DB と軽量配布 DB の両方を検査し、拒否された対応が正規化表へ入らないようにします。

入力 URL、SHA-256、サイズ、取得メタデータを記録します。検証済みの Anime Mapping DB を固定してローカルで参照します。最新の収録数とサイズは README の固定値ではなく manifest を参照してください。

```bash
anime-timestamp-db audit \
  --db artifacts/timestamps.db \
  --evidence-db artifacts/timestamps-evidence.db
```

## 利用上の境界

このプロジェクトは anime-db-bot の必須依存ではありません。通常ビルドで配信サイトを巡回せず、すべての作品に区間があるとは保証しません。収録数を増やすための無理な話数対応も行いません。

## ドキュメント

- [Schema and resolver contract](../docs/SCHEMA.md)
- [API crawling, checkpoints, and publishing](../docs/CRAWLING.md)
- [API source notice](../ANIME_SKIP_API_NOTICE.md) · [Open Anime Timestamps notice](../OPEN_ANIME_TIMESTAMPS_NOTICE.md)
- [Data licensing](../DATA_LICENSE.md) · [Third-party notices](../THIRD_PARTY_NOTICES.md)

## ライセンスと出典

コードは Apache-2.0 です。生成データには元データセットと API の規約が適用されます。明示的なデータライセンスがないソースもあるため、再配布前に通知文書を確認してください。 [Apache-2.0](../LICENSE) · [DATA_LICENSE.md](../DATA_LICENSE.md) · [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
