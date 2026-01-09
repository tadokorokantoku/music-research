#!/usr/bin/env python3
"""
Create or update daily annotation issue for YouTube MV reports
"""
import re
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict

def parse_report(file_path: Path) -> Dict:
    """Parse a single report file and extract videos"""
    content = file_path.read_text()

    # Extract time from filename (mv_HH.md)
    time_match = re.search(r'mv_(\d{2})\.md$', file_path.name)
    hour = time_match.group(1) if time_match else '??'

    videos = {
        'high_quality': [],  # 🌟 確実な日本MV
        'japan_mv': [],      # ✅ 日本MV
        'candidates': []     # 🔍 要確認
    }

    # Split into sections
    sections = {
        '🌟 確実な日本MV': 'high_quality',
        '✅ 日本MV': 'japan_mv',
        '🔍 要確認': 'candidates'
    }

    current_section = None
    for line in content.split('\n'):
        # Detect section
        for marker, key in sections.items():
            if marker in line:
                current_section = key
                break

        # Parse video line
        if current_section and line.startswith('| ') and re.match(r'\| \d+ \|', line):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 11:
                video = {
                    'title': parts[2],
                    'channel': parts[3],
                    'country': parts[4],
                    'time': parts[5],
                    'duration': parts[6],
                    'views': parts[7],
                    'mv_score': parts[8],
                    'jp_score': parts[9],
                    'link': parts[10]
                }
                videos[current_section].append(video)

    return {'hour': hour, 'videos': videos}

def format_section(title: str, hour: str, videos: List[Dict]) -> str:
    """Format a section with videos as markdown table"""
    if not videos:
        return ''

    md = f"## {title} ({hour}:00実行分)\n\n"
    md += "| 除外 | タイトル | チャンネル | MV | JP | リンク | 除外理由 |\n"
    md += "|------|---------|----------|-----|-----|--------|----------|\n"

    for v in videos:
        md += f"| [ ] | {v['title']} | {v['channel']} | {v['mv_score']} | {v['jp_score']} | {v['link']} | <!-- ここに理由を記入 --> |\n"

    md += "\n---\n\n"
    return md

def create_issue_body(reports: List[Dict]) -> str:
    """Create issue body from all reports"""
    body = "# 動画レビュー\n\n"
    body += "除外したい動画にチェック ✅ を付けて、理由を記入してください。\n"
    body += "記入後、ラベルを `needs-review` から `reviewed` に変更すると自動で除外ルールが更新されます。\n\n"
    body += "---\n\n"

    section_titles = {
        'high_quality': '🌟 確実な日本MV',
        'japan_mv': '✅ 日本MV',
        'candidates': '🔍 要確認'
    }

    for report in reports:
        hour = report['hour']
        videos = report['videos']

        for key, title in section_titles.items():
            body += format_section(title, hour, videos[key])

    return body

def main():
    if len(sys.argv) < 2:
        print("Usage: create_annotation_issue.py <date:YYMMDD>")
        sys.exit(1)

    date_str = sys.argv[1]

    # Find all reports for the date
    docs_dir = Path(__file__).parent.parent / 'docs' / date_str
    if not docs_dir.exists():
        print(f"No reports found for {date_str}")
        sys.exit(1)

    report_files = sorted(docs_dir.glob('mv_*.md'))
    if not report_files:
        print(f"No report files found in {docs_dir}")
        sys.exit(1)

    # Parse all reports
    reports = []
    for f in report_files:
        report = parse_report(f)
        # Skip if no videos
        if any(report['videos'][k] for k in ['high_quality', 'japan_mv', 'candidates']):
            reports.append(report)

    if not reports:
        print(f"No videos found in reports for {date_str}")
        sys.exit(0)

    # Create issue body
    body = create_issue_body(reports)

    # Output to file for gh issue
    output_file = Path('/tmp') / f'issue_body_{date_str}.md'
    output_file.write_text(body)

    print(f"✅ Issue body created: {output_file}")
    print(f"   Found {len(reports)} reports with videos")

    return str(output_file)

if __name__ == '__main__':
    main()
