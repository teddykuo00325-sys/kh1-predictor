"""Flask dashboard for the prediction system."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, redirect, url_for

from . import (analyzer, backtest, daily_tasks, db, dress_strategy,
                level_data, lootbox_data, notify, predictor)
from .feedback import bp as feedback_bp

ROOT = Path(__file__).resolve().parent.parent
app = Flask(__name__, template_folder=str(ROOT / "templates"), static_folder=str(ROOT / "static"))
app.register_blueprint(feedback_bp)

# Ensure schema exists on every cold start, even on a fresh container where
# build-time scraping somehow didn't run. Predictor pages will simply show
# zero data until the operator triggers an extract.
db.init_schema()


def _article_count() -> int:
    try:
        with db.connect() as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
    except Exception:
        return 0


@app.route("/healthz")
def healthz():
    """Used by Render's health check.  Always returns 200 even if DB is empty
    so the service is not marked unhealthy before the first scrape lands."""
    return jsonify({
        "ok": True,
        "articles": _article_count(),
        "version": "1.2",
        # Capability flags — booleans only, real values stay secret.
        "admin_configured": bool(os.environ.get("ADMIN_TOKEN")),
        "telegram_configured": notify.configured(),
    })


@app.route("/admin/test-telegram")
def admin_test_telegram():
    """Token-protected diagnostic: synchronously POST a test message via the
    server's notify module and return the raw outcome.  Reveals exactly why
    Telegram isn't pushing (env vars missing / 401 / DNS error / etc)."""
    token = os.environ.get("ADMIN_TOKEN", "")
    provided = request.args.get("key") or ""
    import hmac
    if not token or not provided or not hmac.compare_digest(provided, token):
        return jsonify({"error": "not found"}), 404
    ok, info = notify.send_telegram(
        "🧪 <b>診斷測試</b>\n如果你收到此訊息，代表 production 容器可以正常呼叫 Telegram API。"
    )
    return jsonify({
        "telegram_configured": notify.configured(),
        "ok": ok,
        "info": info,
    })


@app.route("/")
def dashboard():
    if _article_count() == 0:
        return render_template("empty.html"), 200
    # Month mode is opt-in via ?month=YYYY-MM, else use the rolling window.
    month_param = request.args.get("month")
    if month_param:
        try:
            y, m = month_param.split("-")
            p = predictor.predict(date(int(y), int(m), 1))
        except Exception:
            p = predictor.predict_rolling()
    else:
        try:
            back  = int(request.args.get("back",  predictor.DEFAULT_LOOK_BACK_DAYS))
            ahead = int(request.args.get("ahead", predictor.DEFAULT_LOOK_FORWARD_DAYS))
        except ValueError:
            back, ahead = predictor.DEFAULT_LOOK_BACK_DAYS, predictor.DEFAULT_LOOK_FORWARD_DAYS
        back  = max(0,  min(180, back))
        ahead = max(7, min(180, ahead))
        p = predictor.predict_rolling(look_back=back, look_forward=ahead)
    return render_template("dashboard.html", p=p)


@app.route("/timeline")
def timeline():
    acts = analyzer.load_activities()
    # group by year-month for the timeline
    buckets: dict[str, list[dict]] = {}
    for a in acts:
        key = f"{a['year']}-{a['month']:02d}"
        buckets.setdefault(key, []).append(a)
    ordered = sorted(buckets.items(), reverse=True)
    return render_template("timeline.html", buckets=ordered)


@app.route("/activities")
def activities():
    kind = request.args.get("kind", "")
    q = request.args.get("q", "").strip()
    sql = ("SELECT a.*, ar.publish_date, ar.title AS article_title "
           "FROM activities a JOIN articles ar ON ar.id = a.article_id WHERE 1=1")
    params: list = []
    if kind:
        sql += " AND a.kind=?"
        params.append(kind)
    if q:
        sql += " AND (a.name LIKE ? OR a.description LIKE ? OR a.keywords LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like, like])
    sql += " ORDER BY ar.publish_date DESC LIMIT 500"
    with db.connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return render_template("activities.html", rows=rows, kind=kind, q=q)


@app.route("/accuracy")
def accuracy():
    """Historical backtest results: how often did the predictor's calls come true."""
    try:
        min_history = max(2, int(request.args.get("min_history", 2)))
    except ValueError:
        min_history = 2
    report = backtest.run_backtest(min_history_years=min_history)
    return render_template("accuracy.html", report=report, min_history=min_history)


@app.route("/recurring")
def recurring():
    """Yearly recurrence statistics: which activities cycle multiple times a year."""
    try:
        min_avg = float(request.args.get("min", 2.0))
    except ValueError:
        min_avg = 2.0
    try:
        min_years = int(request.args.get("years", 2))
    except ValueError:
        min_years = 2
    kind = request.args.get("kind", "")
    rows = analyzer.yearly_recurrence_stats(min_avg_per_year=min_avg,
                                              min_years_active=min_years)
    if kind:
        rows = [r for r in rows if r["kind"] == kind]
    today = date.today()
    return render_template("recurring.html",
                            rows=rows, min_avg=min_avg, min_years=min_years,
                            kind=kind, today=today.isoformat())


@app.route("/lootbox")
@app.route("/lootbox/<box_id>")
def lootbox_page(box_id: str = ""):
    """福袋期望值分析."""
    box_id = box_id or (lootbox_data.LOOTBOXES[0].id if lootbox_data.LOOTBOXES else "")
    box = lootbox_data.get_box(box_id)
    if not box:
        return redirect(url_for("lootbox_page"))

    try:
        target_count = max(1, min(99, int(request.args.get("target", 1))))
    except ValueError:
        target_count = 1
    channel_for_calc = request.args.get("channel", box.purchase_channels[0].label)

    # 實測校正參數
    try:
        obs_draws = int(request.args.get("obs_draws", 0))
    except ValueError:
        obs_draws = 0
    try:
        obs_stars = int(request.args.get("obs_stars", 0))
    except ValueError:
        obs_stars = 0
    obs_analysis = None
    if obs_draws > 0 and obs_stars >= 0:
        obs_analysis = lootbox_data.analyze_observation(box, obs_draws, obs_stars)

    return render_template("lootbox.html",
        all_boxes=lootbox_data.LOOTBOXES,
        box=box,
        rewards=lootbox_data.reward_breakdown(box),
        ev=lootbox_data.total_ev_per_draw(box),
        sigma=lootbox_data.sigma_per_draw(box),
        prob_sum=lootbox_data.prob_sum(box),
        channels=lootbox_data.channel_analysis(box),
        target_count=target_count,
        channel_for_calc=channel_for_calc,
        target_result=lootbox_data.calc_for_target(box, channel_for_calc, target_count),
        obs_draws=obs_draws,
        obs_stars=obs_stars,
        obs_analysis=obs_analysis,
    )


@app.route("/dress-strategy")
def dress_strategy_page():
    """扮裝加持策略 — +1~+20 道具使用對照與 SOP."""
    # Per-item current-level calculator
    item_levels: list[int] = []
    next_steps: list[dict] = []
    for i in range(1, 7):
        try:
            lv = int(request.args.get(f"item{i}", 0))
        except ValueError:
            lv = 0
        lv = max(0, min(20, lv))
        item_levels.append(lv)
        next_steps.append(dress_strategy.next_step_for(lv))
    return render_template("dress_strategy.html",
        policies=dress_strategy.POLICIES,
        stages=dress_strategy.STAGES,
        never_use=dress_strategy.NEVER_USE,
        purchase_plan=dress_strategy.PURCHASE_PLAN,
        sop=dress_strategy.SOP,
        item_levels=item_levels,
        next_steps=next_steps,
    )


@app.route("/daily")
def daily():
    """每日任務執行清單 — 常駐 + 當前活動限定."""
    today = date.today()
    buckets = daily_tasks.tasks_for(today)
    return render_template("daily.html",
                            today=today.isoformat(),
                            buckets=buckets)


@app.route("/levels")
def levels():
    """Character XP requirements + martial-essence (戰技精隨) lookup."""
    # XP A->B calculator inputs
    try:
        from_lvl = max(1, min(260, int(request.args.get("from", 1))))
        to_lvl   = max(1, min(260, int(request.args.get("to",   260))))
    except ValueError:
        from_lvl, to_lvl = 1, 260
    if to_lvl < from_lvl:
        from_lvl, to_lvl = to_lvl, from_lvl

    xp_needed, unknown_levels = level_data.xp_between(from_lvl, to_lvl)
    cum_total, cum_unknown    = level_data.cumulative_xp_to(260)

    # Leveling-time calculator: XP per hour → time breakdown
    try:
        xp_per_hour = int(request.args.get("xph", 0))
    except ValueError:
        xp_per_hour = 0
    time_estimate = None
    if xp_per_hour > 0 and xp_needed > 0:
        total_hours = xp_needed / xp_per_hour
        time_estimate = {
            "xp_per_hour": xp_per_hour,
            "total_hours": total_hours,
            "days_24h": total_hours / 24,
            "days_12h": total_hours / 12,
            "days_8h":  total_hours / 8,
            "days_4h":  total_hours / 4,
        }
    known_ranges    = level_data.known_level_ranges()
    missing_ranges  = level_data.missing_level_ranges(260)
    total_known_xp  = sum(level_data.XP_TO_REACH.values())

    # Full table data (1..260) for the big table
    table_rows = []
    cumulative = 0
    for lvl in range(2, 261):
        xp = level_data.XP_TO_REACH.get(lvl)
        if xp is not None:
            cumulative += xp
        table_rows.append({
            "level": lvl,
            "xp_to_reach": xp,
            "cumulative_if_known": cumulative if xp is not None else None,
        })

    # Martial essence — flatten into one row per range
    essence_total_breakdown = level_data.total_essence_to_cap()
    essence_total = level_data.TOTAL_ESSENCE_TO_CAP_OVERRIDE or essence_total_breakdown

    return render_template("levels.html",
        xp_data=level_data.XP_TO_REACH,
        table_rows=table_rows,
        known_ranges=known_ranges,
        missing_ranges=missing_ranges,
        total_known_xp=total_known_xp,
        from_lvl=from_lvl, to_lvl=to_lvl,
        xp_needed=xp_needed, unknown_levels=unknown_levels,
        time_estimate=time_estimate,
        essence_ranges=level_data.MARTIAL_ESSENCE_RANGES,
        essence_total=essence_total,
        essence_total_breakdown=essence_total_breakdown,
        level_cap=level_data.LEVEL_CAP,
        level_cap_fill_xp=level_data.LEVEL_CAP_FILL_XP,
        E=100_000_000,
    )


@app.route("/recharge")
def recharge():
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT g.*, ar.publish_date, ar.title
               FROM recharge_gifts g
               JOIN articles ar ON ar.id = g.article_id
               ORDER BY ar.publish_date DESC"""
        ).fetchall()
    return render_template("recharge.html", rows=rows)


@app.route("/article/<int:aid>")
def article(aid: int):
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
        if not row:
            return redirect(url_for("dashboard"))
        acts = conn.execute(
            "SELECT * FROM activities WHERE article_id=? ORDER BY seq", (aid,)
        ).fetchall()
        gifts = conn.execute(
            "SELECT * FROM recharge_gifts WHERE article_id=?", (aid,)
        ).fetchall()
    html = ""
    if row["html_path"]:
        p = db.ROOT / row["html_path"]
        if p.exists():
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(p.read_text(encoding="utf-8", errors="ignore"), "lxml")
            content = soup.select_one("div.newstxt")
            html = str(content) if content else ""
    return render_template("article.html", article=row, activities=acts, gifts=gifts, body_html=html)


def main():
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
