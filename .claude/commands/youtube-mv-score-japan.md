# youtube-mv-score-japan

動画データとチャンネル情報に対して日本スコア（0-100点）を計算します。
**日本の動画かどうか**のみを評価します。

## 実行内容

JSONファイルから動画データとチャンネル情報を読み込み、日本スコアを計算して結果を保存します。

## 入力

- `/tmp/videos_{YYMMDD}_{HH}.json`: 動画詳細情報
- `/tmp/channels_{YYMMDD}_{HH}.json`: チャンネル情報

## 出力

- `/tmp/japan_scores_{YYMMDD}_{HH}.json`: 日本スコア結果

```json
[
  {
    "id": "lBZCZ3m5hCI",
    "japan_score": 100,
    "japan_reasons": "チャンネル国=JP",
    "details": {
      "channel_country": "JP",
      "default_language": "ja",
      "has_japanese_title": true,
      "has_japanese_brackets": true,
      "japanese_ratio_description": 0.85
    }
  },
  ...
]
```

## スコアリングロジック（0-100点）

### A. チャンネル国設定（最優先・即確定）

```python
if channel_info.get('country') == 'JP':
    return 100, 'チャンネル国=JP'  # 即100点確定
```

**理由**: チャンネル設定が日本なら、ほぼ確実に日本のコンテンツ

### B. 言語設定（高信頼度）

```python
if video['snippet'].get('defaultLanguage') == 'ja':
    score += 80
    reasons.append('+80(defaultLanguage=ja)')
```

**理由**: 動画の言語設定が日本語なら、信頼度が高い

### C. タイトルの日本語（中信頼度）

```python
# 日本語文字（ひらがな、カタカナ、漢字）を含むか
if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', title):
    score += 30
    reasons.append('+30(タイトル日本語)')

# 日本特有の記号【】『』「」
if re.search(r'[【】『』「」]', title) and has_japanese(title):
    score += 10
    reasons.append('+10(日本記号)')
```

**注意**: 記号だけではダメ。日本語文字も含まれている必要あり（ネパール等の誤検出防止）

### D. 説明文の日本語（低信頼度）

```python
japanese_ratio = calculate_japanese_ratio(description)

if japanese_ratio >= 0.5:  # 50%以上が日本語
    score += 20
    reasons.append('+20(説明文50%+日本語)')
elif japanese_ratio >= 0.1:  # 10%以上が日本語
    score += 10
    reasons.append('+10(説明文10%+日本語)')
```

### E. 他国チャンネルの減点

```python
if channel_info.get('country') and channel_info.get('country') != 'JP':
    score -= 50
    reasons.append(f"-50(チャンネル国={channel_info.get('country')})")
```

**理由**: チャンネル国が明示的に他国の場合、日本コンテンツの可能性は低い

### 最終調整

```python
score = max(0, min(100, score))  # 0-100の範囲に収める
```

## 実装

```python
#!/usr/bin/env python3
import json
import re

def has_japanese(text):
    """日本語文字を含むか"""
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))

def japanese_ratio(text):
    """日本語の割合を計算"""
    if not text:
        return 0
    japanese_chars = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))
    total_chars = len(re.sub(r'\s', '', text))  # 空白を除く
    if total_chars == 0:
        return 0
    return japanese_chars / total_chars

def calc_japan_score(video, channel_info):
    """日本スコア計算"""
    snippet = video['snippet']
    title = snippet.get('title', '')
    description = snippet.get('description', '')

    score = 0
    reasons = []
    details = {}

    # チャンネル情報
    channel_country = channel_info.get('country', '')
    details['channel_country'] = channel_country

    # A. チャンネル国設定（最優先）
    if channel_country == 'JP':
        return {
            'id': video['id'],
            'japan_score': 100,
            'japan_reasons': 'チャンネル国=JP',
            'details': details
        }

    # B. 言語設定
    default_language = snippet.get('defaultLanguage', '')
    details['default_language'] = default_language
    if default_language == 'ja':
        score += 80
        reasons.append('+80(defaultLanguage=ja)')

    # C. タイトルの日本語
    has_jp_title = has_japanese(title)
    details['has_japanese_title'] = has_jp_title
    if has_jp_title:
        score += 30
        reasons.append('+30(タイトル日本語)')

    has_jp_brackets = bool(re.search(r'[【】『』「」]', title)) and has_jp_title
    details['has_japanese_brackets'] = has_jp_brackets
    if has_jp_brackets:
        score += 10
        reasons.append('+10(日本記号)')

    # D. 説明文の日本語
    jp_ratio = japanese_ratio(description)
    details['japanese_ratio_description'] = round(jp_ratio, 2)
    if jp_ratio >= 0.5:
        score += 20
        reasons.append('+20(説明文50%+日本語)')
    elif jp_ratio >= 0.1:
        score += 10
        reasons.append('+10(説明文10%+日本語)')

    # E. 他国チャンネルの減点
    if channel_country and channel_country != 'JP':
        score -= 50
        reasons.append(f"-50(チャンネル国={channel_country})")

    score = max(0, min(100, score))

    return {
        'id': video['id'],
        'japan_score': score,
        'japan_reasons': ', '.join(reasons) if reasons else '判定不可',
        'details': details
    }

# メイン処理
def main(date_hour_str):
    """
    date_hour_str: YYMMDD_HH 形式 (例: "260108_14")
    """
    # データ読み込み
    with open(f'/tmp/videos_{date_hour_str}.json', 'r') as f:
        videos = json.load(f)

    with open(f'/tmp/channels_{date_hour_str}.json', 'r') as f:
        channels_list = json.load(f)

    # チャンネル情報を辞書化
    channels = {}
    for ch in channels_list:
        channels[ch['id']] = {
            'country': ch['snippet'].get('country', ''),
            'title': ch['snippet'].get('title', '')
        }

    # スコアリング
    results = []
    stats = {
        'channel_jp': 0,
        'channel_other': 0,
        'channel_unknown': 0
    }

    for video in videos:
        channel_id = video['snippet']['channelId']
        channel_info = channels.get(channel_id, {})

        # 統計
        country = channel_info.get('country', '')
        if country == 'JP':
            stats['channel_jp'] += 1
        elif country:
            stats['channel_other'] += 1
        else:
            stats['channel_unknown'] += 1

        result = calc_japan_score(video, channel_info)
        results.append(result)

    # 保存
    with open(f'/tmp/japan_scores_{date_hour_str}.json', 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ 日本スコア計算完了: {len(results)}件")
    print(f"\nチャンネル国設定:")
    print(f"  - 日本(JP): {stats['channel_jp']}件")
    print(f"  - その他: {stats['channel_other']}件")
    print(f"  - 不明: {stats['channel_unknown']}件")

    # スコア分布
    jp_100 = sum(1 for r in results if r['japan_score'] == 100)
    jp_70_99 = sum(1 for r in results if 70 <= r['japan_score'] < 100)
    jp_50_69 = sum(1 for r in results if 50 <= r['japan_score'] < 70)

    print(f"\nスコア分布:")
    print(f"  - JP=100: {jp_100}件")
    print(f"  - JP 70-99: {jp_70_99}件")
    print(f"  - JP 50-69: {jp_50_69}件")

if __name__ == '__main__':
    import sys
    from datetime import datetime, timezone, timedelta

    if len(sys.argv) > 1:
        date_hour_str = sys.argv[1]
    else:
        # デフォルト: 現在のJST時刻
        jst = timezone(timedelta(hours=9))
        now_jst = datetime.now(jst)
        date_hour_str = now_jst.strftime('%y%m%d_%H')

    main(date_hour_str)
```

## 改善履歴

### v3.1: 記号判定の厳格化
- **問題**: ネパールアーティストが「」記号だけで日本判定されていた
- **改善**: 記号 + 日本語文字の両方が必須に変更

### v3.2: チャンネル国を最優先に
- **追加**: channel.country='JP' → 即100点確定
- **理由**: 最も信頼性の高い指標

## 他国への拡張

将来的に韓国、アメリカ等のMVも収集する場合:

```python
# youtube-mv-score-korea.md
if channel_info.get('country') == 'KR':
    return 100, 'チャンネル国=KR'

if snippet.get('defaultLanguage') == 'ko':
    score += 80

# ハングル文字
if re.search(r'[\uAC00-\uD7AF]', title):
    score += 30
```

同様のロジックで他国版を作成可能。
