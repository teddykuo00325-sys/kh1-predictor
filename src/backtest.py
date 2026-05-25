"""Historical backtest: how well would the predictor have done if we had
deployed it at the start of each past year?

For each festival anchored in target year Y, we:
  1. Restrict the dataset to publications from years < Y (everything the
     predictor would have known back then).
  2. Compute the set of activity signatures historically tied to that festival
     across the known years — these are our PREDICTIONS for festival Y.
  3. Compare against the ACTUAL signatures that appeared in festival Y's
     ±14-day window.

Output stats:
  precision = hits / predicted        (did our predictions come true?)
  recall    = hits / actual           (did we predict everything that came?)
  surprises = actual but not predicted (new activities that broke the pattern)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from . import analyzer, festivals
from .cache import ttl_cache


FESTIVAL_WINDOW_DAYS = 14


def _festival_date(fest: festivals.Festival, year: int) -> date | None:
    if fest.name.startswith("母親節"):
        return festivals.mothers_day(year)
    return fest.solar_date(year)


def _matches_festival_window(a: dict, fest: festivals.Festival,
                              win_start: date, win_end: date) -> bool:
    """Same matching logic as the live predictor."""
    text = f"{a['name']} {a['description']} {a['reward']}"
    if any(k and k in text for k in fest.keywords):
        return True
    try:
        pub = date.fromisoformat(a["publish_date"][:10])
    except (ValueError, TypeError):
        return False
    return win_start <= pub <= win_end


@dataclass
class FestivalResult:
    year: int
    festival: str
    festival_date: str
    predicted_count: int
    actual_count: int
    hits: list[str]
    misses: list[str]
    surprises: list[str]

    @property
    def precision(self) -> float:
        return len(self.hits) / self.predicted_count if self.predicted_count else 0.0

    @property
    def recall(self) -> float:
        return len(self.hits) / self.actual_count if self.actual_count else 0.0


@ttl_cache(900)        # 15 min — heavy, rarely changes
def run_backtest(min_target_year: int = 2024, min_history_years: int = 2) -> dict:
    """Replay the predictor through `min_target_year`-onward festivals.

    Only signatures that appeared in at least `min_history_years` distinct prior
    years are counted as predictions (consistent with the dashboard's
    "強候選 ≥2 年" rule).  This eliminates noise from one-off activities that
    happened to fall near a festival in any single past year.
    """
    acts = analyzer.load_activities()
    clean = [a for a in acts if not analyzer._is_noise(a)]

    target_years = sorted({a["year"] for a in clean if a["year"] >= min_target_year})
    festival_results: list[FestivalResult] = []

    for target_year in target_years:
        known  = [a for a in clean if a["year"] <  target_year]
        actual = [a for a in clean if a["year"] == target_year]
        if not known:
            continue

        for fest in festivals.FESTIVALS:
            target_date = _festival_date(fest, target_year)
            if not target_date:
                continue
            t_start = target_date - timedelta(days=FESTIVAL_WINDOW_DAYS)
            t_end   = target_date + timedelta(days=FESTIVAL_WINDOW_DAYS)

            # Predicted signatures: sigs whose past appearances are spread across
            # at least `min_history_years` distinct years of the same festival window.
            sig_years: dict[str, set[int]] = defaultdict(set)
            for a in known:
                fy = a["year"]
                d_fy = _festival_date(fest, fy)
                if not d_fy:
                    continue
                k_start = d_fy - timedelta(days=FESTIVAL_WINDOW_DAYS)
                k_end   = d_fy + timedelta(days=FESTIVAL_WINDOW_DAYS)
                if _matches_festival_window(a, fest, k_start, k_end):
                    key = analyzer._activity_key(a)
                    if key and len(key) >= 2:
                        sig_years[key].add(fy)
            predicted_sigs: set[str] = {
                sig for sig, ys in sig_years.items() if len(ys) >= min_history_years
            }

            # Actual signatures: from THIS year's festival window
            actual_sigs: set[str] = set()
            for a in actual:
                if _matches_festival_window(a, fest, t_start, t_end):
                    key = analyzer._activity_key(a)
                    if key and len(key) >= 2:
                        actual_sigs.add(key)

            # Drop fests with no signal at all
            if not predicted_sigs and not actual_sigs:
                continue

            hits      = sorted(predicted_sigs & actual_sigs)
            misses    = sorted(predicted_sigs - actual_sigs)
            surprises = sorted(actual_sigs   - predicted_sigs)
            festival_results.append(FestivalResult(
                year=target_year,
                festival=fest.name,
                festival_date=target_date.isoformat(),
                predicted_count=len(predicted_sigs),
                actual_count=len(actual_sigs),
                hits=hits, misses=misses, surprises=surprises,
            ))

    # Aggregate
    by_year: dict[int, dict] = defaultdict(lambda: {"predicted": 0, "hits": 0,
                                                      "actual": 0, "surprises": 0,
                                                      "festivals": 0})
    by_festival: dict[str, dict] = defaultdict(lambda: {"predicted": 0, "hits": 0,
                                                          "actual": 0, "events": 0})
    overall_pred = overall_hits = overall_actual = overall_surprises = 0

    for r in festival_results:
        by_year[r.year]["predicted"]  += r.predicted_count
        by_year[r.year]["hits"]       += len(r.hits)
        by_year[r.year]["actual"]     += r.actual_count
        by_year[r.year]["surprises"]  += len(r.surprises)
        by_year[r.year]["festivals"]  += 1
        by_festival[r.festival]["predicted"] += r.predicted_count
        by_festival[r.festival]["hits"]      += len(r.hits)
        by_festival[r.festival]["actual"]    += r.actual_count
        by_festival[r.festival]["events"]    += 1
        overall_pred      += r.predicted_count
        overall_hits      += len(r.hits)
        overall_actual    += r.actual_count
        overall_surprises += len(r.surprises)

    def safe_div(a, b): return a / b if b else 0.0
    for y, v in by_year.items():
        v["precision"] = round(safe_div(v["hits"], v["predicted"]) * 100, 1)
        v["recall"]    = round(safe_div(v["hits"], v["actual"])    * 100, 1)
    for f, v in by_festival.items():
        v["precision"] = round(safe_div(v["hits"], v["predicted"]) * 100, 1)
        v["recall"]    = round(safe_div(v["hits"], v["actual"])    * 100, 1)

    return {
        "overall": {
            "precision":      round(safe_div(overall_hits, overall_pred)   * 100, 1),
            "recall":         round(safe_div(overall_hits, overall_actual) * 100, 1),
            "predicted":      overall_pred,
            "hits":           overall_hits,
            "actual":         overall_actual,
            "surprises":      overall_surprises,
            "festivals_evaluated": len(festival_results),
            "target_years":   target_years,
        },
        "by_year":     dict(by_year),
        "by_festival": dict(by_festival),
        "details": [r.__dict__ for r in festival_results],
    }


def _print_report(report: dict) -> None:
    o = report["overall"]
    print(f"\n=== 預測準確度回測 ({len(report['details'])} 個節日場次) ===")
    print(f"涵蓋年份：{o['target_years']}")
    print(f"預測 {o['predicted']} 條樣板，命中 {o['hits']} 條，實際出現 {o['actual']} 條")
    print(f"  precision (預測命中率): {o['precision']}%")
    print(f"  recall    (實際捕捉率): {o['recall']}%")
    print(f"  surprises (未預測到的新活動): {o['surprises']} 條")

    print("\n[按年份]")
    print(f"{'年份':<6} {'場次':<5} {'預測':<5} {'命中':<5} {'實際':<5} {'precision':>10} {'recall':>8}")
    for y in sorted(report["by_year"]):
        v = report["by_year"][y]
        print(f"{y:<6} {v['festivals']:<5} {v['predicted']:<5} {v['hits']:<5} {v['actual']:<5}"
              f" {v['precision']:>9}% {v['recall']:>7}%")

    print("\n[按節日 Top 10]")
    fests = sorted(report["by_festival"].items(),
                    key=lambda x: -x[1]["predicted"])[:10]
    print(f"{'節日':<24} {'次數':<4} {'預測':<5} {'命中':<5} {'precision':>10}")
    for name, v in fests:
        print(f"{name:<23} {v['events']:<4} {v['predicted']:<5} {v['hits']:<5} {v['precision']:>9}%")


def main():
    _print_report(run_backtest())


if __name__ == "__main__":
    main()
