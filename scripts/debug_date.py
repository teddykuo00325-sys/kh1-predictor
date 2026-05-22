"""Trace why DATE_RANGE_RE fails on real activity time strings."""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import extractor, db
from bs4 import BeautifulSoup

# 1. Look at the raw time string from article #1544
with db.connect() as conn:
    row = conn.execute("SELECT html_path FROM articles WHERE id=1544").fetchone()
p = db.ROOT / row['html_path']
soup = BeautifulSoup(p.read_text(encoding='utf-8'), 'lxml')
content = soup.select_one('div.newstxt')

# Find the first activity block and print its body
blocks = extractor._segment_blocks(str(content))
print(f"Total blocks: {len(blocks)}\n")
for i, (title, body) in enumerate(blocks[:3]):
    print(f"--- block {i}: {title!r}")
    print(f"body (repr): {body[:300]!r}")
    fields = extractor._bracket_split(body)
    print(f"bracket fields: {list(fields.keys())}")
    if "活動時間" in fields:
        t = fields["活動時間"]
        print(f"  raw time string: {t!r}")
        m = extractor.DATE_RANGE_RE.search(t)
        print(f"  regex match: {m}")
        if m:
            print(f"  groups: {m.groups()}")
        start, end = extractor.parse_date_range(t, 2026)
        print(f"  parsed: start={start} end={end}")
    print()
