"""Find which 2026 activities collide with historical signature '群英副本通關'."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import analyzer, predictor

acts = analyzer.load_activities()
print("=== signatures of historical 群英副本 ===")
for a in acts:
    if "群英副本" in (a["name"] or ""):
        print(f"  year={a['year']}  key='{predictor._activity_key(a)}'  start={a['start_dt']}  end={a['end_dt']}  name={a['name'][:40]}")

print("\n=== ALL 2026 activities whose key starts with '群英副本' or normalised name does ===")
for a in [x for x in acts if x['year'] == 2026]:
    k = predictor._activity_key(a)
    if k.startswith("群英") or "群英" in (a["name"] or ""):
        print(f"  key='{k}'  start={a['start_dt']}  end={a['end_dt']}  name={a['name'][:50]}")

print("\n=== 2026 activities collapsed to key '群英副本通關' ===")
TARGET = "群英副本通關"
for a in [x for x in acts if x['year'] == 2026]:
    if predictor._activity_key(a) == TARGET:
        print(f"  start={a['start_dt']}  end={a['end_dt']}  pub={a['publish_date']}  name={a['name'][:60]}")
