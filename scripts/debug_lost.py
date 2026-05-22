"""Check which articles lost their multi-activity structure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import db
from bs4 import BeautifulSoup

with db.connect() as conn:
    rows = conn.execute("""
        SELECT ar.id, ar.publish_date, ar.title, COUNT(a.id) as n
        FROM articles ar LEFT JOIN activities a ON a.article_id = ar.id
        GROUP BY ar.id
        HAVING n <= 1
        ORDER BY ar.publish_date DESC
        LIMIT 8
    """).fetchall()
    print("articles with <=1 activity:")
    for r in rows:
        print(f"  #{r['id']} {r['publish_date']} ({r['n']} acts) {r['title'][:50]}")

    # inspect one
    r = conn.execute("""
        SELECT id, html_path, title FROM articles WHERE id=:id
    """, {"id": rows[0]['id']}).fetchone() if rows else None
    if r:
        print(f"\nINSPECTING #{r['id']}:")
        p = db.ROOT / r['html_path']
        soup = BeautifulSoup(p.read_text(encoding='utf-8'), 'lxml')
        content = soup.select_one('div.newstxt')
        if content:
            for tag in ['p', 'div', 'h2', 'h3', 'br']:
                print(f"  <{tag}> count: {len(content.find_all(tag, recursive=True))}")
            strongs = content.find_all('strong')
            print(f"  <strong> count: {len(strongs)}")
            print(f"  first 3 strong texts: {[s.get_text(strip=True)[:30] for s in strongs[:3]]}")
            # Check what type of element wraps the strongs
            for s in strongs[:5]:
                parent = s.parent
                while parent and parent.name == 'span':
                    parent = parent.parent
                print(f"    '{s.get_text(strip=True)[:25]}' wrapped in <{parent.name if parent else '?'}>")
