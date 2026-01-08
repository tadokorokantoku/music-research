# youtube-mv-score-mv

動画データに対してMVスコア（0-100点）を計算します。
**国は一切考慮せず**、MVとしての品質のみを評価します。

## 実行内容

JSONファイルから動画データを読み込み、MVスコアを計算して結果を保存します。

## 入力

- `/tmp/videos_{YYMMDD}.json`: 動画詳細情報

## 出力

- `/tmp/mv_scores_{YYMMDD}.json`: MVスコア結果

```json
[
  {
    "id": "lBZCZ3m5hCI",
    "mv_score": 60,
    "mv_reasons": "+20(MV), +10(Official), +15(標準長), +10(説明充実), +5(配信)",
    "details": {
      "has_mv_keyword": true,
      "has_official": true,
      "has_credits": false,
      "has_streaming_links": true,
      "duration_sec": 264,
      "description_length": 1234
    }
  },
  ...
]
```

## スコアリングロジック（0-100点）

### A. タイトルのキーワード（最大30点）

```python
if re.search(r'\bMV\b|Music Video|ミュージックビデオ', title, re.IGNORECASE):
    score += 20  # "MV" / "Music Video" / "ミュージックビデオ"

if 'Official Video' in title or 'Official MV' in title:
    score += 10  # "Official Video" / "Official MV"
```

### B. 制作情報（最大20点）

```python
# 制作クレジット（厳格化版）
# 単なる単語マッチではなく、実際にクレジット形式か確認
credit_patterns = [
    r'監督[：:\s]+[^\s]+',
    r'Director[：:\s]+[^\s]+',
    r'演出[：:\s]+[^\s]+',
    r'撮影[：:\s]+[^\s]+',
    r'編集[：:\s]+[^\s]+',
    r'Produced by[：:\s]+[^\s]+'
]

if any(re.search(pattern, description) for pattern in credit_patterns):
    score += 15  # 実際のクレジット記載あり

# 配信導線リンク
streaming_links = ['Spotify', 'Apple Music', 'LINE MUSIC', 'linkco.re', 'lnk.to']
if any(link in description for link in streaming_links):
    score += 5  # 配信導線あり
```

### C. 公式性（最大20点）

```python
if 'Official' in title:
    score += 10  # タイトルに "Official"

if any(word in channel_title for word in ['Official', '公式', 'VEVO']):
    score += 10  # 公式チャンネル
```

### D. 長さの妥当性（最大15点）

```python
duration_sec = parse_duration(video['contentDetails']['duration'])

if 180 <= duration_sec <= 300:  # 3-5分
    score += 15  # 標準的なMVの長さ
elif 120 <= duration_sec < 180 or 300 < duration_sec <= 360:  # 2-3分 or 5-6分
    score += 10  # やや短い/長いが許容範囲
elif 60 <= duration_sec < 120 or 360 < duration_sec <= 480:  # 1-2分 or 6-8分
    score += 5   # かなり短い/長いが一応許容
```

### E. 品質指標（最大15点）

```python
if len(description) >= 500:
    score += 10  # 説明文が充実（500字以上）

# 将来的な拡張用
# if '4K' in title or 'HD' in title:
#     score += 5  # 高画質
```

### F. 減点項目

```python
# カバー・歌ってみた
if any(word in title.lower() or word in description.lower()
       for word in ['cover', 'カバー', '歌ってみた', '踊ってみた', '弾いてみた']):
    score -= 40

# Reaction動画
if any(word in title.lower() or word in description.lower()
       for word in ['reaction', 'リアクション', 'react to']):
    score -= 30

# ライブ映像
if 'Live' in title or 'ライブ' in title or 'LIVE' in title:
    if 'Official Live Video' in title:
        score -= 5   # 公式ライブは軽減
    else:
        score -= 15  # 通常のライブ

# Lyric Video
if 'Lyric Video' in title or 'リリックビデオ' in title or '歌詞付き' in title:
    score -= 10

# Shorts
if duration_sec < 60 or '#shorts' in title.lower() or '#shorts' in description.lower():
    score -= 100  # 即除外レベル

# AI生成（新規追加）
if any(keyword in description for keyword in ['AI Generation', 'AI生成', 'Suno', 'AI-generated']):
    score -= 20  # AI生成コンテンツ
```

### 最終調整

```python
score = max(0, min(100, score))  # 0-100の範囲に収める
```

## 実装

```python
#!/usr/bin/env python3
import json
import re

def parse_duration(duration):
    """ISO 8601 duration → 秒数"""
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds

def calc_mv_score(video):
    """MVスコア計算"""
    snippet = video['snippet']
    title = snippet.get('title', '')
    description = snippet.get('description', '')
    channel_title = snippet.get('channelTitle', '')
    duration_sec = parse_duration(video['contentDetails']['duration'])

    score = 0
    reasons = []
    details = {}

    # A. タイトルのキーワード
    has_mv_keyword = bool(re.search(r'\bMV\b|Music Video|ミュージックビデオ', title, re.IGNORECASE))
    if has_mv_keyword:
        score += 20
        reasons.append('+20(MV)')
    details['has_mv_keyword'] = has_mv_keyword

    if 'Official Video' in title or 'Official MV' in title:
        score += 10
        reasons.append('+10(Official Video)')

    # B. 制作情報
    credit_patterns = [
        r'監督[：:\s]+[^\s]+',
        r'Director[：:\s]+[^\s]+',
        r'演出[：:\s]+[^\s]+',
        r'撮影[：:\s]+[^\s]+',
        r'編集[：:\s]+[^\s]+',
        r'Produced by[：:\s]+[^\s]+'
    ]
    has_credits = any(re.search(pattern, description) for pattern in credit_patterns)
    if has_credits:
        score += 15
        reasons.append('+15(制作)')
    details['has_credits'] = has_credits

    streaming_links = ['Spotify', 'Apple Music', 'LINE MUSIC', 'linkco.re', 'lnk.to']
    has_streaming = any(link in description for link in streaming_links)
    if has_streaming:
        score += 5
        reasons.append('+5(配信)')
    details['has_streaming_links'] = has_streaming

    # C. 公式性
    has_official_title = 'Official' in title
    if has_official_title:
        score += 10
        reasons.append('+10(Official)')
    details['has_official'] = has_official_title

    if any(word in channel_title for word in ['Official', '公式', 'VEVO']):
        score += 10
        reasons.append('+10(公式ch)')

    # D. 長さ
    details['duration_sec'] = duration_sec
    if 180 <= duration_sec <= 300:
        score += 15
        reasons.append('+15(標準長)')
    elif 120 <= duration_sec < 180 or 300 < duration_sec <= 360:
        score += 10
        reasons.append('+10(適切長)')
    elif 60 <= duration_sec < 120 or 360 < duration_sec <= 480:
        score += 5
        reasons.append('+5(やや長短)')

    # E. 品質指標
    details['description_length'] = len(description)
    if len(description) >= 500:
        score += 10
        reasons.append('+10(説明充実)')

    # F. 減点項目
    if any(word in title.lower() or word in description.lower()
           for word in ['cover', 'カバー', '歌ってみた', '踊ってみた', '弾いてみた']):
        score -= 40
        reasons.append('-40(カバー等)')

    if any(word in title.lower() or word in description.lower()
           for word in ['reaction', 'リアクション', 'react to']):
        score -= 30
        reasons.append('-30(Reaction)')

    if 'Live' in title or 'ライブ' in title or 'LIVE' in title:
        if 'Official Live Video' in title:
            score -= 5
            reasons.append('-5(公式Live)')
        else:
            score -= 15
            reasons.append('-15(Live)')

    if 'Lyric Video' in title or 'リリックビデオ' in title or '歌詞付き' in title:
        score -= 10
        reasons.append('-10(Lyric)')

    if duration_sec < 60 or '#shorts' in title.lower() or '#shorts' in description.lower():
        score -= 100
        reasons.append('-100(Shorts)')

    if any(keyword in description for keyword in ['AI Generation', 'AI生成', 'Suno', 'AI-generated']):
        score -= 20
        reasons.append('-20(AI生成)')

    score = max(0, min(100, score))

    return {
        'id': video['id'],
        'mv_score': score,
        'mv_reasons': ', '.join(reasons),
        'details': details
    }

# メイン処理
def main(target_date):
    date_str = target_date.replace('-', '')[2:]  # YYMMDD

    with open(f'/tmp/videos_{date_str}.json', 'r') as f:
        videos = json.load(f)

    results = []
    for video in videos:
        result = calc_mv_score(video)
        results.append(result)

    with open(f'/tmp/mv_scores_{date_str}.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ MVスコア計算完了: {len(results)}件")

    # 統計
    high = sum(1 for r in results if r['mv_score'] >= 70)
    medium = sum(1 for r in results if 50 <= r['mv_score'] < 70)
    low = sum(1 for r in results if 30 <= r['mv_score'] < 50)

    print(f"  - MV≥70: {high}件")
    print(f"  - MV 50-69: {medium}件")
    print(f"  - MV 30-49: {low}件")

if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else '2026-01-07')
```

## 改善履歴

### v3.1: 制作クレジット判定を厳格化
- **問題**: 「制作によせて」のような文章でも+15点されていた
- **改善**: 正規表現で「監督: ○○」形式のみ認識

### v3.2: AI生成コンテンツ検出
- **追加**: AI生成を検出して-20点
- **理由**: 個人制作のAIコンテンツを除外
