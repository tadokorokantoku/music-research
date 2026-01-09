---
description: YouTube Data APIを使って過去N時間の日本の音楽MV動画を効率的に収集し、2軸スコアリングしてレポートを作成する
---

# youtube-mv

YouTube Data APIを使って、過去N時間に投稿された日本の音楽MV動画を検索し、2軸スコアリング（MVスコア × 日本スコア）でノイズを除去してレポートを作成します。

## 使い方

```bash
/youtube-mv [hours]
```

- **hours**: 過去何時間分のデータを取得するか（デフォルト: 24）
  - 例: `/youtube-mv 1` → 過去1時間分
  - 例: `/youtube-mv 24` → 過去24時間分（1日分）
  - 例: `/youtube-mv` → 過去24時間分（デフォルト）

## 概要

このコマンドは3つのサブコマンドを順番に実行します:

1. **`/youtube-mv-fetch {hours}`**: データ取得
2. **`/youtube-mv-score-mv`**: MVスコアリング（0-100点）
3. **`/youtube-mv-score-japan`**: 日本スコアリング（0-100点）
4. **レポート生成**: 2軸スコアでフィルタリング・分類

## 実行手順

### Step 0: 除外リスト読み込み（スキップ可能）

`data/exclusions.json` が存在する場合、除外ルールを読み込みます。このファイルには以下が含まれます：
- 除外する動画ID
- チャンネル名/タイトルのパターン
- スコアリング調整ルール

### Step 1: データ取得

```
/youtube-mv-fetch {hours}
```

**実行内容**:
- YouTube Data API v3で検索（3クエリ × 1ページ）
- videos.listで動画詳細取得
- channels.listでチャンネル情報取得
- JSON出力: `/tmp/videos_{YYMMDD}.json`, `/tmp/channels_{YYMMDD}.json`

**APIコスト**: 約306 units

### Step 2: MVスコアリング

```
/youtube-mv-score-mv
```

**実行内容**:
- タイトル、制作クレジット、公式性、長さを評価
- 0-100点のMVスコアを計算
- JSON出力: `/tmp/mv_scores_{YYMMDD}.json`

**評価項目**:
- タイトルキーワード（MV, Music Video）
- 制作クレジット（厳格化: 正規表現で「監督: ○○」形式）
- 公式性（Official, 公式ch）
- 長さ（3-5分が標準）
- AI生成検出（-20点）

### Step 3: 日本スコアリング

```
/youtube-mv-score-japan
```

**実行内容**:
- チャンネル国、言語設定、日本語比率を評価
- 0-100点の日本スコアを計算
- JSON出力: `/tmp/japan_scores_{YYMMDD}.json`

**評価項目**:
- チャンネル国=JP（即100点）
- defaultLanguage=ja（+80点）
- タイトル日本語（+30点）
- 日本記号【】（+10点）
- 説明文日本語比率

### Step 4: レポート生成

スコアをマージして最終レポートを生成します。

#### 4.1 スコアマージ

```python
#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 日付+時刻（現在のJST日時でファイル名を特定）
jst = timezone(timedelta(hours=9))
now_jst = datetime.now(jst)
date_hour_str = now_jst.strftime('%y%m%d_%H')  # 例: 260108_14

# データ読み込み
with open(f'/tmp/videos_{date_hour_str}.json', 'r') as f:
    videos = json.load(f)

with open(f'/tmp/mv_scores_{date_hour_str}.json', 'r') as f:
    mv_scores = json.load(f)

with open(f'/tmp/japan_scores_{date_hour_str}.json', 'r') as f:
    japan_scores = json.load(f)

# 除外リスト読み込み
exclusions = {'videos': [], 'patterns': [], 'scoring_rules': {'rules': []}}
exclusions_file = Path('data/exclusions.json')
if exclusions_file.exists():
    with open(exclusions_file, 'r') as f:
        exclusions = json.load(f)
    print(f"📋 除外リスト読み込み: {len(exclusions['videos'])}件の動画, {len(exclusions['patterns'])}件のパターン")

# スコア辞書化
mv_dict = {item['id']: item for item in mv_scores}
jp_dict = {item['id']: item for item in japan_scores}

# 除外動画IDセット
excluded_video_ids = {v['video_id'] for v in exclusions['videos']}

# マージ
results = {
    'high_quality': [],  # MV≥70 & JP=100
    'japan_mv': [],      # MV≥50 & JP≥70
    'candidates': [],    # MV≥30 & JP≥50
    'excluded': []
}

for video in videos:
    vid = video['id']
    mv_data = mv_dict.get(vid, {})
    jp_data = jp_dict.get(vid, {})

    mv_score = mv_data.get('mv_score', 0)
    jp_score = jp_data.get('japan_score', 0)

    # 除外リストチェック
    if vid in excluded_video_ids:
        results['excluded'].append({
            'id': vid,
            'title': video['snippet']['title'],
            'reason': '除外リストに登録済み'
        })
        continue

    # パターンマッチングでスコア調整
    title = video['snippet']['title']
    channel = video['snippet']['channelTitle']

    for pattern in exclusions['patterns']:
        pattern_type = pattern.get('pattern_type')
        pattern_regex = pattern.get('pattern')
        penalty = pattern.get('score_penalty', 0)

        if pattern_type == 'channel_name' and re.search(pattern_regex, channel):
            mv_score += penalty
            print(f"  🔧 {channel}: MVスコア {penalty:+d}点調整")
        elif pattern_type == 'title_keyword' and re.search(pattern_regex, title):
            mv_score += penalty
            print(f"  🔧 {title}: MVスコア {penalty:+d}点調整")

    # スコアリングルール適用
    for rule in exclusions.get('scoring_rules', {}).get('rules', []):
        # TODO: ルール適用ロジックを実装
        pass

    # Shorts除外
    if mv_score < 0:  # Shortsは-100点
        results['excluded'].append({
            'id': vid,
            'title': video['snippet']['title'],
            'reason': 'Shorts'
        })
        continue

    # マージデータ
    item = {
        'id': vid,
        'title': video['snippet']['title'],
        'channel': video['snippet']['channelTitle'],
        'channel_country': jp_data.get('details', {}).get('channel_country', '不明'),
        'published': video['snippet']['publishedAt'],
        'duration_sec': mv_data.get('details', {}).get('duration_sec', 0),
        'views': video['statistics'].get('viewCount', '0'),
        'mv_score': mv_score,
        'mv_reasons': mv_data.get('mv_reasons', ''),
        'jp_score': jp_score,
        'jp_reasons': jp_data.get('japan_reasons', '')
    }

    # 分類
    if mv_score >= 70 and jp_score == 100:
        results['high_quality'].append(item)
    elif mv_score >= 50 and jp_score >= 70:
        results['japan_mv'].append(item)
    elif mv_score >= 30 and jp_score >= 50:
        results['candidates'].append(item)
    else:
        results['excluded'].append({
            'id': vid,
            'title': video['snippet']['title'],
            'reason': f'MV={mv_score}, JP={jp_score}'
        })

# ソート
for category in ['high_quality', 'japan_mv', 'candidates']:
    results[category].sort(key=lambda x: (x['mv_score'], x['jp_score']), reverse=True)

# 保存
with open(f'/tmp/merged_results_{date_hour_str}.json', 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"✅ スコアマージ完了")
print(f"  - 確実な日本MV: {len(results['high_quality'])}件")
print(f"  - 日本MV: {len(results['japan_mv'])}件")
print(f"  - 要確認: {len(results['candidates'])}件")
```

#### 4.2 Markdownレポート生成

`/tmp/merged_results_{YYMMDD}_{HH}.json` から Markdownレポート `docs/{YYMMDD}/mv_{HH}.md` を生成してください。

**実行方法**: Pythonスクリプトを作成して実行してください。

**実装手順**:
1. `/tmp/merged_results_{YYMMDD}_{HH}.json` を読み込む
2. `/tmp/metadata_{YYMMDD}_{HH}.json` からメタデータ（実行時刻、対象期間、APIコスト）を取得
3. 以下の構成でMarkdownテキストを生成:
   - **ヘッダー**: `# YouTube MV 新着レポート ({YYYY-MM-DD HH:00})`
   - **サマリー**: 件数統計、APIコスト、対象期間
   - **🌟 確実な日本MV**: MV≥70 & JP=100 のテーブル（スコア降順）
   - **✅ 日本MV**: MV≥50 & JP≥70 のテーブル（スコア降順）
   - **🔍 要確認**: MV≥30 & JP≥50 のテーブル（スコア降順）
   - **採用基準説明**: 2軸スコアリングの説明
4. `docs/{YYMMDD}` ディレクトリを作成（`mkdir -p`）
5. `docs/{YYMMDD}/mv_{HH}.md` にレポートを保存

**テーブル形式**:
```markdown
| # | タイトル | チャンネル | 国 | 公開時刻 | 長さ | 再生回数 | MV | JP | リンク |
|---|---------|----------|-----|---------|------|---------|-----|-----|--------|
| 1 | タイトル | チャンネル名 | JP | 14:30 | 3:45 | 1,234 | 85 | 100 | [▶️](https://youtube.com/watch?v=...) |
```

**完了メッセージ**:
```
✅ レポート生成完了
  出力: docs/{YYMMDD}/mv_{HH}.md
  確実な日本MV: X件
  日本MV: X件
  要確認: X件
```

例: `docs/260108/mv_14.md` (2026年1月8日14時実行分)

#### 4.3 アノテーション用Issue作成/更新

レポート生成後、当日のアノテーション用Issueを作成または更新します。

**実行方法**:
```bash
# Issue作成スクリプトを実行
python3 scripts/create_annotation_issue.py {YYMMDD}

# 当日のIssueを検索
ISSUE_NUMBER=$(gh issue list --label "mv-annotation" --search "in:title [MV Annotation] {YYYY-MM-DD}" --json number --jq '.[0].number')

if [ -z "$ISSUE_NUMBER" ]; then
  # 新規作成
  gh issue create --title "[MV Annotation] {YYYY-MM-DD} の動画レビュー" \
    --body-file /tmp/issue_body_{YYMMDD}.md \
    --label "mv-annotation,needs-review"
else
  # 既存Issueに追記
  CURRENT_BODY=$(gh issue view $ISSUE_NUMBER --json body --jq '.body')
  NEW_SECTION=$(cat /tmp/issue_body_{YYMMDD}.md | sed -n '/^## /,$p')

  echo "$CURRENT_BODY" > /tmp/updated_body.md
  echo "" >> /tmp/updated_body.md
  echo "$NEW_SECTION" >> /tmp/updated_body.md

  gh issue edit $ISSUE_NUMBER --body-file /tmp/updated_body.md
fi
```

**完了メッセージ**:
```
✅ アノテーション用Issue更新完了
  Issue: #{ISSUE_NUMBER}
```

## 採用基準（2軸スコアリング）

```
🌟 確実な日本MV: MVスコア≥70 AND 日本スコア=100
  → チャンネル国が日本で、MV品質も高い

✅ 日本MV: MVスコア≥50 AND 日本スコア≥70
  → 日本の動画である可能性が高く、MV品質も十分

🔍 要確認: MVスコア≥30 AND 日本スコア≥50
  → MVまたは日本判定のスコアがやや低い

❌ 除外: 上記以外
```

## 出力

### JSONファイル（`/tmp`）

```
/tmp/videos_{YYMMDD}_{HH}.json         # 動画詳細
/tmp/channels_{YYMMDD}_{HH}.json       # チャンネル情報
/tmp/mv_scores_{YYMMDD}_{HH}.json      # MVスコア
/tmp/japan_scores_{YYMMDD}_{HH}.json   # 日本スコア
/tmp/merged_results_{YYMMDD}_{HH}.json # マージ結果
```

### Markdownレポート

```
docs/{YYMMDD}/mv_{HH}.md
```

## 戦略（190件の日本MV分析に基づく）

### 検索最適化
- **高精度**: defaultLanguage="ja"が100%の信頼シグナル
- **効率重視**: 3つの最適クエリで十分な拾得率
- **ノイズ除去**: 制作クレジット（94%）と配信導線（76%）で品質判定

### スコアリング改善
- **v3.1**: 制作クレジット判定を厳格化（正規表現で実名確認）
- **v3.2**: AI生成コンテンツ検出（-20点）
- **v3.3**: 2軸スコアリング導入（MV × 日本）

## APIコスト

```
検索: 300 units (3クエリ × 100 units)
videos.list: 3 units
channels.list: 3 units
合計: 306 units / 10,000 (3.06%)
```

## トラブルシューティング

### Q. 公式MVが取得できない

A. 検索の並び順が`relevance`だと、公開直後の動画が上位50件に入らない可能性があります。`order=date`に変更するか、ページ数を増やしてください。

### Q. 個人制作のAIコンテンツが高スコア

A. `/youtube-mv-score-mv`のv3.2でAI生成検出を追加しました。説明文に"AI Generation"等があれば-20点されます。

### Q. 制作クレジットの誤検出

A. v3.1で正規表現による厳格化を実施。「制作によせて」等の文章では加点されません。

## 改善履歴

### v4.0 (2026-01-09)
- アノテーション機能追加
  - GitHub Issue経由で除外動画を収集
  - 1日単位でIssue作成、毎時追記
  - ラベル変更（`needs-review` → `reviewed`）で自動処理
- 除外リスト（data/exclusions.json）導入
  - 動画ID、パターン、スコアリング調整ルールを管理
  - スコアマージ時に自動適用
- scripts/create_annotation_issue.py 追加
- scripts/process_annotations.py 追加
- .github/workflows/process-annotations.yml 追加

### v3.6 (2026-01-08)
- レポート生成の指示を明確化
- 「Pythonスクリプトを作成して実行してください」を追加
- テーブル形式とメタデータ取得方法を具体化

### v3.5 (2026-01-08)
- ファイル名に実行時刻（時）を追加
- `/tmp/videos_{YYMMDD}_{HH}.json` 形式に変更
- `docs/{YYMMDD}/mv_{HH}.md` でレポート保存
- 同日に複数回実行しても上書きされない

### v3.4 (2026-01-08)
- hours引数を追加（過去N時間分のデータを取得）
- デフォルト24時間
- `/youtube-mv 1` で過去1時間、`/youtube-mv 24` で過去24時間

### v3 (2026-01-08)
- 2軸スコアリング導入（MV × 日本）
- チャンネル国情報を追加（channels.list API）
- スキル分割（fetch, score-mv, score-japan）

### v2 (2026-01-08)
- 日本判定を厳格化（記号 + 日本語文字必須）
- ネパール等の誤検出を防止

### v1 (2026-01-07)
- 初版リリース
- 190件の日本MV分析に基づく最適化
