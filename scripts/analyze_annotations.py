#!/usr/bin/env python3
"""
Analyze annotation reasons and generate generalized scoring rules using LLM
"""
import json
import sys
from pathlib import Path

def create_analysis_prompt(videos: list) -> str:
    """Create prompt for LLM to analyze annotations"""

    prompt = """# アノテーション分析タスク

以下の除外された動画のリストから、**汎用的で過適合しない**スコアリングルールを生成してください。

## 重要な方針
1. **過適合を避ける**: その動画だけを弾くためのルールではなく、同じ特徴を持つ動画全般に適用できるルールを作る
2. **正常なMVを誤検出しない**: 保守的に調整し、本物の公式MVに影響しないようにする
3. **本質的な特徴を抽出**: 表面的なキーワードマッチではなく、本質的な問題点を見つける

## 除外された動画

"""

    for i, v in enumerate(videos, 1):
        mv_score = v.get('mv_score', '不明')
        jp_score = v.get('jp_score', '不明')
        prompt += f"""
### {i}. {v['title']}
- **チャンネル**: {v['channel']}
- **MVスコア**: {mv_score}
- **日本スコア**: {jp_score}
- **除外理由**: {v['reason']}
"""

    prompt += """

## 生成すべきルール

各ルールは以下の形式で、**具体的で適用範囲が明確**なものを生成してください：

```json
{
  "rule_type": "title_pattern | channel_pattern | language_detection | video_category",
  "pattern": "正規表現またはキーワード",
  "score_adjustment": {
    "mv_score": -XX,
    "japan_score": -XX
  },
  "reason": "なぜこの調整が必要か",
  "example_matches": ["マッチする例1", "マッチする例2"],
  "false_positive_check": "正常なMVでマッチしないことを確認する観点"
}
```

## 分析観点

1. **言語・地域の誤判定**
   - 中国語（簡体字・繁体字）の動画が日本MVとして誤検出されていないか
   - タイトルやチャンネル名から判断できる特徴は？

2. **動画カテゴリの誤判定**
   - MVではない動画（解説、リアクション、ライブ映像など）が混入していないか
   - チャンネル名やタイトルから判断できる特徴は？

3. **公式性の誤判定**
   - 個人制作や非公式ファン動画が高スコアになっていないか
   - クレジットの有無以外に判断できる特徴は？

4. **アーカイブ・再投稿の誤判定**
   - 古い映像の再投稿が新作MVとして扱われていないか
   - タイトルから判断できる特徴は？

## 出力形式

JSON配列として、3-5個の汎用的なルールを生成してください。各ルールは上記の形式に従ってください。
"""

    return prompt

def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_annotations.py <exclusions_json_path>")
        sys.exit(1)

    exclusions_file = Path(sys.argv[1])

    if not exclusions_file.exists():
        print(f"Exclusions file not found: {exclusions_file}")
        sys.exit(1)

    # Load exclusions
    with open(exclusions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    videos = data.get('videos', [])

    if not videos:
        print("No annotated videos found")
        sys.exit(0)

    # Create analysis prompt
    prompt = create_analysis_prompt(videos)

    # Output prompt to file for LLM analysis
    output_file = Path('/tmp/annotation_analysis_prompt.txt')
    output_file.write_text(prompt, encoding='utf-8')

    print(f"✅ Analysis prompt created: {output_file}")
    print(f"   Videos analyzed: {len(videos)}")
    print()
    print("Next step: Run this prompt through Claude Code or LLM to generate scoring rules")
    print()
    print(prompt)

if __name__ == '__main__':
    main()
