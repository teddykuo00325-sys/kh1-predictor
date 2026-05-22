"""Flask dashboard for the prediction system."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, render_template, request, redirect, url_for

from . import analyzer, db, predictor
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
        "version": "1.1",
        # Whether the operator has configured the admin-page token (true/false
        # only — the actual value is never disclosed).
        "admin_configured": bool(os.environ.get("ADMIN_TOKEN")),
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
