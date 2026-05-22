"""Find the article that contains the 2026 群英副本 activity and check its time string."""
import sys, sqlite3
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import db
from bs4 import BeautifulSoup

with db.connect() as conn:
    row = conn.execute("""
        SELECT a.article_id, a.seq, a.name, a.description, a.start_dt, a.end_dt, ar.publish_date, ar.html_path
        FROM activities a JOIN articles ar ON ar.id=a.article_id
        WHERE a.name LIKE '%群英副本通關%' AND ar.publish_date >= '2026-01-01'
    """).fetchall()
    for r in row:
        print(f"article #{r['article_id']} pub={r['publish_date']} seq={r['seq']}")
        print(f"  name: {r['name']}")
        print(f"  start={r['start_dt']}  end={r['end_dt']}")
        print(f"  description: {r['description'][:300]}")
        print()
        # Show the raw paragraph around it
        p = db.ROOT / r['html_path']
        soup = BeautifulSoup(p.read_text(encoding='utf-8'), 'lxml')
        content = soup.select_one('div.newstxt')
        if content:
            txt = content.get_text("\n", strip=True)
            idx = txt.find("群英副本通關")
            if idx != -1:
                print("--- raw context ---")
                print(txt[max(0,idx-40):idx+500])
                print()
