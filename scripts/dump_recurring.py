"""Print yearly recurrence stats in readable form."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import analyzer

stats = analyzer.yearly_recurrence_stats(min_avg_per_year=2.0)
print(f"Total signatures with avg ≥ 2/year & ≥ 2 years active: {len(stats)}\n")
print(f"{'活動':<28} {'年均':>5} {'總次數':>5} {'年數':>4}  {'上次':<11} {'預估下次':<11}  {'各月':24}  各年")
print("-" * 130)
for r in stats:
    months = "".join(f"{r['month_distribution'][m]:1}" if r['month_distribution'][m] < 10 else "+" for m in range(1,13))
    per_year = " ".join(f"{y}:{c}" for y,c in sorted(r['per_year_counts'].items()))
    print(f"{r['name_example'][:25]:<26}  {r['avg_per_year']:>5}  {r['total_count']:>5}  {r['years_active']:>4}  "
          f"{r['last_occurrence'] or '?':<11}  {r['predicted_next_date'] or '?':<11}  "
          f"{months:<24}  {per_year}")
