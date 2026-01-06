---
description: 日本の音楽ニュースサイトのRSSフィードから最新リリース情報を収集してレポートを作成する
---

日本の音楽ニュースサイトのRSSフィードから、今日配信された記事を収集し、音楽リリースレポートを作成してください。

## 手順

### 1. 日付取得・ディレクトリ作成

```bash
TODAY=$(date +%Y-%m-%d)
YYMMDD=$(date +%y%m%d)
mkdir -p docs/${YYMMDD}
```

### 2. RSSフィード取得（優先順）

以下のRSSフィードからWebFetchで**今日配信された記事のみ**を取得：

1. **必須** - ナタリー: https://natalie.mu/music/feed
2. **推奨** - BARKS: https://www.barks.jp/feed/
3. **推奨** - OTOTOY: https://ototoy.jp/feature/rss
4. **任意** - Spincoaster: https://spincoaster.com/feed
5. **任意** - Mikiki: https://mikiki.tokyo.jp/rss
6. **任意** - TuneCore: https://www.tunecore.co.jp/blog/feed

### 3. フィルタリング

- **日付**: pubDateが今日の記事のみ
- **キーワード**: リリース/発売/配信開始/新曲/新アルバム/MV公開

### 4. レポート出力

`docs/{YYMMDD}/summary.md` に以下の形式で出力：

```markdown
# 音楽リリースレポート

**取得日時**: YYYY-MM-DD HH:MM
**対象日**: YYYY-MM-DD

---

## 📀 新着リリース

| アーティスト | 作品名 | 種類 | リリース日 | ソース |
|-------------|--------|------|-----------|--------|

## 🎬 MV公開

| アーティスト | 曲名 | 公開日 | ソース |
|-------------|------|--------|--------|

## 📊 サマリー

- **総リリース数**: XX件
```

### 5. 完了報告

出力したファイルパスを表示してください。
