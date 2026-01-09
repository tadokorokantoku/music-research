#!/usr/bin/env python3
"""
Process checked annotations from GitHub Issue and update exclusion list
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

def parse_issue_body(body: str):
    """Parse issue body and extract checked videos with reasons"""
    checked_videos = []

    # Split into lines
    lines = body.split('\n')

    for line in lines:
        # Check for checked checkbox in table row (support both [x] and emoji ✅)
        line_lower = line.lower()
        if (line.startswith('| [x]') or line.startswith('| [X]') or
            '| [✅' in line or '| [☑' in line or '| [✓' in line):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 7:
                # Extract video info
                title = parts[2]
                channel = parts[3]
                mv_score = parts[4]
                jp_score = parts[5]
                link = parts[6]
                reason = parts[7] if len(parts) > 7 else ''

                # Extract video ID from link
                video_id_match = re.search(r'watch\?v=([a-zA-Z0-9_-]+)', link)
                if video_id_match:
                    video_id = video_id_match.group(1)

                    # Clean reason (remove HTML comments)
                    reason = re.sub(r'<!--.*?-->', '', reason).strip()

                    if reason:  # Only add if reason is provided
                        checked_videos.append({
                            'video_id': video_id,
                            'title': title,
                            'channel': channel,
                            'mv_score': int(mv_score) if mv_score.isdigit() else 0,
                            'jp_score': int(jp_score) if jp_score.isdigit() else 0,
                            'reason': reason
                        })

    return checked_videos

def extract_patterns(videos: list) -> dict:
    """Extract common patterns from exclusion reasons

    NOTE: This is a simple pattern extraction. For more sophisticated analysis,
    run: python3 scripts/analyze_annotations.py data/exclusions.json
    This will generate a prompt for LLM to create generalized scoring rules.
    """
    patterns = {
        'channel_patterns': [],
        'title_keywords': [],
        'scoring_adjustments': []
    }

    # Simple pattern extraction for backward compatibility
    reasons_text = '\n'.join([v['reason'] for v in videos])

    # Detect common channel patterns
    if 'ちゃんねる' in reasons_text or '個人' in reasons_text:
        patterns['channel_patterns'].append({
            'pattern_type': 'channel_name',
            'pattern': '.*ちゃんねる$',
            'score_penalty': -20,
            'reason': '個人チャンネルは公式MVの可能性が低い'
        })

    # Detect common title keywords
    if 'LIVE' in reasons_text or 'ライブ' in reasons_text:
        patterns['title_keywords'].append({
            'pattern_type': 'title_keyword',
            'pattern': '.*(LIVE MV|ライブ).*',
            'score_penalty': -30,
            'reason': 'ライブ映像は通常のMVとは異なる'
        })

    if '非公式' in reasons_text:
        patterns['title_keywords'].append({
            'pattern_type': 'title_keyword',
            'pattern': '.*非公式.*',
            'score_penalty': -40,
            'reason': '非公式ファン動画'
        })

    if 'AI' in reasons_text or 'AI生成' in reasons_text:
        patterns['scoring_adjustments'].append({
            'pattern_type': 'title_keyword',
            'pattern': '.*(AI生成|AI|#ai).*',
            'score_penalty': -25,
            'reason': 'AI生成コンテンツ'
        })

    print()
    print("💡 For more sophisticated pattern analysis, run:")
    print("   python3 scripts/analyze_annotations.py data/exclusions.json")

    return patterns

def update_exclusions(exclusions_file: Path, new_videos: list, issue_number: str):
    """Update exclusions.json with new videos and patterns"""
    # Load existing exclusions
    if exclusions_file.exists():
        with open(exclusions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {
            'version': '1.0',
            'last_updated': None,
            'videos': [],
            'patterns': [],
            'scoring_rules': {'description': '動的に学習したスコアリング調整ルール', 'rules': []}
        }

    # Get existing video IDs
    existing_ids = {v['video_id'] for v in data['videos']}

    # Add new videos
    added_count = 0
    for video in new_videos:
        if video['video_id'] not in existing_ids:
            data['videos'].append({
                'video_id': video['video_id'],
                'title': video['title'],
                'channel': video['channel'],
                'reason': video['reason'],
                'date_added': datetime.now().strftime('%Y-%m-%d'),
                'issue_number': issue_number
            })
            added_count += 1

    # Extract and add patterns
    new_patterns = extract_patterns(new_videos)

    # Get existing patterns
    existing_patterns = {p['pattern'] for p in data['patterns']}

    # Add new channel patterns
    for pattern in new_patterns['channel_patterns']:
        if pattern['pattern'] not in existing_patterns:
            data['patterns'].append(pattern)

    # Add new title keyword patterns
    for pattern in new_patterns['title_keywords']:
        if pattern['pattern'] not in existing_patterns:
            data['patterns'].append(pattern)

    # Update last_updated
    data['last_updated'] = datetime.now().isoformat()

    # Save
    with open(exclusions_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 除外リスト更新完了")
    print(f"  新規追加: {added_count}件の動画")
    print(f"  パターン: {len(data['patterns'])}件")

    return data

def main():
    if len(sys.argv) < 2:
        print("Usage: process_annotations.py <issue_body_file>")
        sys.exit(1)

    issue_body_file = Path(sys.argv[1])
    issue_number = sys.argv[2] if len(sys.argv) > 2 else 'unknown'

    if not issue_body_file.exists():
        print(f"Issue body file not found: {issue_body_file}")
        sys.exit(1)

    # Read issue body
    body = issue_body_file.read_text(encoding='utf-8')

    # Parse checked videos
    checked_videos = parse_issue_body(body)

    if not checked_videos:
        print("No checked videos found in issue")
        sys.exit(0)

    print(f"📋 チェックされた動画: {len(checked_videos)}件")
    for v in checked_videos:
        print(f"  - {v['title']}: {v['reason']}")

    # Update exclusions
    exclusions_file = Path(__file__).parent.parent / 'data' / 'exclusions.json'
    exclusions_file.parent.mkdir(parents=True, exist_ok=True)

    update_exclusions(exclusions_file, checked_videos, issue_number)

if __name__ == '__main__':
    main()
