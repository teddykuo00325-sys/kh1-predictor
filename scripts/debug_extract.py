"""Inspect the extraction quality."""
import sqlite3, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import db

with db.connect() as conn:
    print("=== noisy 'activity' rows (these are extraction failures) ===")
    rows = conn.execute("""
        SELECT a.article_id, ar.publish_date, a.name, a.kind
        FROM activities a JOIN articles ar ON ar.id=a.article_id
        WHERE a.name LIKE '%無標題%' OR a.name IN ('消費金額','活動獎勵','獎勵說明','活動說明','活動時間')
        LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"#{r['article_id']} {r['publish_date']}  [{r['kind']}]  {r['name']}")

    print("\n=== sample of recharge_gifts (look for broken parsing) ===")
    for r in conn.execute("SELECT article_id, threshold, gift_qty, gift_name, raw_text FROM recharge_gifts LIMIT 10").fetchall():
        print(f"#{r['article_id']} threshold={r['threshold']} qty={r['gift_qty']} gift='{r['gift_name'][:40]}'  raw='{r['raw_text'][:80]}'")

    print("\n=== activity counts by kind ===")
    for r in conn.execute("SELECT kind, COUNT(*) c FROM activities GROUP BY kind ORDER BY c DESC").fetchall():
        print(f"  {r['kind']:<12} {r['c']}")

    print("\n=== one offending article (HTML preview) ===")
    art = conn.execute("""SELECT id, html_path, title FROM articles
                          WHERE id IN (SELECT article_id FROM activities WHERE name='活動獎勵' LIMIT 1)""").fetchone()
    if art:
        p = db.ROOT / art['html_path']
        print(f"article #{art['id']} {art['title']}")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(p.read_text(encoding='utf-8'), 'lxml')
        content = soup.select_one('div.newstxt')
        if content:
            # show first 80 lines
            for i, p in enumerate(content.find_all(['p','div'])[:25]):
                strong = p.find('strong')
                tag = ' STRONG ' if strong and strong.get_text(strip=True) == p.get_text(strip=True) else '       '
                txt = p.get_text(' ', strip=True)[:80]
                print(f"  {i:>2}{tag} {txt}")
