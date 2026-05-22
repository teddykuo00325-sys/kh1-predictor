"""Inspect why 2026 activities aren't being marked 進行中."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import db

with db.connect() as conn:
    rows = conn.execute("""
        SELECT a.article_id, ar.publish_date, a.name, a.start_dt, a.end_dt, a.kind
        FROM activities a JOIN articles ar ON ar.id=a.article_id
        WHERE ar.publish_date >= '2026-04-01'
          AND (a.name LIKE '%戰場較勁%' OR a.name LIKE '%新手化功%' OR a.name LIKE '%祝福晶石%'
               OR a.name LIKE '%勞動節狂歡%' OR a.name LIKE '%大盾%' OR a.name LIKE '%晉升之珠%')
        ORDER BY ar.publish_date
    """).fetchall()
    for r in rows:
        print(f"#{r['article_id']} {r['publish_date']}  [{r['kind']:<8}]  start={r['start_dt']}  end={r['end_dt']}")
        print(f"   name: {r['name']}")
