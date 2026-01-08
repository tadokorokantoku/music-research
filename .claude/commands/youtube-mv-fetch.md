# youtube-mv-fetch

YouTube Data APIを使って音楽MV候補を取得し、JSONファイルとして保存します。

## 実行内容

1. YouTube Data API v3で検索
2. 動画詳細情報を取得（videos.list）
3. チャンネル情報を取得（channels.list）
4. JSON形式で保存

## 入力パラメータ

- **target_date**: 対象日（YYYY-MM-DD形式、省略時は前日）
- **queries**: 検索クエリ（省略時はデフォルト3クエリ）
- **pages_per_query**: クエリごとのページ数（デフォルト: 1）

## 出力

以下のJSONファイルを`/tmp`に出力:
- `videos_{YYMMDD}.json`: 動画詳細情報
- `channels_{YYMMDD}.json`: チャンネル情報
- `metadata_{YYMMDD}.json`: メタデータ（検索条件、実行日時など）

## 検索条件（デフォルト）

```python
検索クエリ: ["MV", "Music Video", "Official Video"]
ページ数: 1ページ/クエリ (50件)
パラメータ:
  - videoCategoryId: 10 (音楽)
  - regionCode: JP
  - relevanceLanguage: ja
  - publishedAfter/Before: 対象日の00:00〜23:59 (JST)
```

## APIコスト

```
検索: 100 units × クエリ数 × ページ数
videos.list: 約1 unit × (動画数 ÷ 50)
channels.list: 約1 unit × (チャンネル数 ÷ 50)

例) 3クエリ × 1ページ:
  - 検索: 300 units
  - videos.list: 3 units
  - channels.list: 3 units
  - 合計: 306 units
```

## 実装手順

### 1. 環境変数確認

```bash
# .env.local から YOUTUBE_API_KEY を取得
APIKEY=$(grep YOUTUBE_API_KEY .env.local | cut -d'=' -f2)
```

### 2. 日付範囲計算

```python
from datetime import datetime, timedelta, timezone

# 対象日（指定なければ前日）
if target_date:
    target = datetime.strptime(target_date, '%Y-%m-%d')
else:
    target = datetime.now() - timedelta(days=1)

# JST → UTC変換
jst = timezone(timedelta(hours=9))
target_jst = target.replace(tzinfo=jst)

# API用のUTC時刻
start_utc = target_jst.replace(hour=0, minute=0, second=0).astimezone(timezone.utc)
end_utc = target_jst.replace(hour=23, minute=59, second=59).astimezone(timezone.utc)

published_after = start_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
published_before = end_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
```

### 3. 検索実行

```bash
for query in "${queries[@]}"; do
    for page in $(seq 1 $pages_per_query); do
        # search.list API呼び出し
        curl -s "https://www.googleapis.com/youtube/v3/search?..." > /tmp/search_${query}_${page}.json
    done
done

# ビデオIDを抽出・重複排除
cat /tmp/search_*.json | ... > /tmp/video_ids.txt
```

### 4. 詳細情報取得

```bash
# 50件ずつバッチ処理
for batch in ...; do
    # videos.list
    curl -s "https://www.googleapis.com/youtube/v3/videos?..." > /tmp/videos_batch${i}.json
done

# マージ
cat /tmp/videos_batch*.json | jq -s 'map(.items) | flatten' > /tmp/videos_{YYMMDD}.json
```

### 5. チャンネル情報取得

```bash
# チャンネルID抽出
cat /tmp/videos_{YYMMDD}.json | jq -r '.[].snippet.channelId' | sort | uniq > /tmp/channel_ids.txt

# 50件ずつバッチ処理
for batch in ...; do
    # channels.list
    curl -s "https://www.googleapis.com/youtube/v3/channels?..." > /tmp/channels_batch${i}.json
done

# マージ
cat /tmp/channels_batch*.json | jq -s 'map(.items) | flatten' > /tmp/channels_{YYMMDD}.json
```

### 6. メタデータ保存

```json
{
  "target_date": "2026-01-07",
  "executed_at": "2026-01-08T18:30:00+09:00",
  "queries": ["MV", "Music Video", "Official Video"],
  "pages_per_query": 1,
  "total_videos": 149,
  "total_channels": 142,
  "api_units_used": 306
}
```

## 出力例

```bash
/tmp/videos_260107.json:
[
  {
    "id": "lBZCZ3m5hCI",
    "snippet": {
      "title": "【大和、沈没】Official Music Video...",
      "channelId": "UC...",
      "publishedAt": "2026-01-07T09:00:00Z",
      "defaultLanguage": "ja",
      ...
    },
    "contentDetails": {
      "duration": "PT4M24S"
    },
    "statistics": {
      "viewCount": "24"
    }
  },
  ...
]

/tmp/channels_260107.json:
[
  {
    "id": "UC...",
    "snippet": {
      "title": "Aoyama Nanami",
      "country": "JP"
    }
  },
  ...
]
```

## エラーハンドリング

- API keyが未設定 → エラーメッセージ
- API制限超過 → 警告メッセージ
- ネットワークエラー → リトライ（最大3回）

## 完了メッセージ

```
✅ データ取得完了

対象日: 2026-01-07
取得動画数: 149件
チャンネル数: 142件
APIコスト: 306 units

出力ファイル:
- /tmp/videos_260107.json
- /tmp/channels_260107.json
- /tmp/metadata_260107.json
```
