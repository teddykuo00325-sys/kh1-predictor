"""Feedback collection: form + admin view.

Free-tier Render note
---------------------
SQLite lives on the container's ephemeral filesystem.  Feedback survives
service sleep/wake cycles but is WIPED on every new deploy (i.e. git push +
auto-deploy).  The /admin/feedback/export endpoint returns JSON so the
operator can back up before deploying.
"""
from __future__ import annotations

import hmac
import json
import os
import time
from datetime import datetime, timedelta

from flask import (Blueprint, abort, redirect, render_template, request,
                   url_for, jsonify, make_response)

from . import db, notify

bp = Blueprint("feedback", __name__)

# in-process rate-limit: ip -> last submit timestamp.  Single-worker gunicorn,
# so this is consistent.
_LAST_SUBMIT: dict[str, float] = {}
RATE_LIMIT_SECONDS = 60

MAX_MESSAGE_LEN = 5000
MAX_NAME_LEN    = 80
MAX_CONTACT_LEN = 120


def _client_ip() -> str:
    """Return the client IP, masking the last octet so we don't store full IPs."""
    raw = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    if not raw:
        return ""
    if ":" in raw:                       # IPv6 — mask the last 16 bits
        parts = raw.split(":")
        return ":".join(parts[:-1] + ["0"])
    parts = raw.split(".")
    if len(parts) == 4:                  # IPv4 — zero the last octet
        return ".".join(parts[:3] + ["0"])
    return raw


def _admin_authorised() -> bool:
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        return False                     # admin disabled if not configured
    provided = request.args.get("key") or request.headers.get("X-Admin-Token", "")
    return bool(provided) and hmac.compare_digest(provided, token)


# ---------------------------------------------------- public form
@bp.route("/feedback", methods=["GET"])
def feedback_form():
    return render_template("feedback.html",
                            max_message_len=MAX_MESSAGE_LEN,
                            error=request.args.get("error"))


@bp.route("/feedback", methods=["POST"])
def feedback_submit():
    # 1) Honeypot — bots fill every input; legit users leave this empty
    if (request.form.get("website") or "").strip():
        # Pretend success, drop on the floor
        return redirect(url_for("feedback.feedback_thanks"))

    # 2) Rate limit per IP
    ip = _client_ip()
    now = time.time()
    last = _LAST_SUBMIT.get(ip, 0)
    if now - last < RATE_LIMIT_SECONDS:
        wait = int(RATE_LIMIT_SECONDS - (now - last))
        return redirect(url_for("feedback.feedback_form",
                                 error=f"操作太頻繁，請 {wait} 秒後再試"))

    # 3) Validation
    name    = (request.form.get("name")    or "").strip()[:MAX_NAME_LEN]
    contact = (request.form.get("contact") or "").strip()[:MAX_CONTACT_LEN]
    message = (request.form.get("message") or "").strip()[:MAX_MESSAGE_LEN]

    if not message:
        return redirect(url_for("feedback.feedback_form", error="請填寫意見內容"))
    if len(message) < 4:
        return redirect(url_for("feedback.feedback_form", error="意見內容太短了"))

    # 4) Persist
    ua = (request.headers.get("User-Agent") or "")[:240]
    submitted_at = datetime.now().isoformat(timespec="seconds")
    with db.cursor() as conn:
        conn.execute(
            "INSERT INTO feedback (name, contact, message, submitted_at, ip, user_agent) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name or None, contact or None, message, submitted_at, ip, ua),
        )
    _LAST_SUBMIT[ip] = now

    # 5) Notify operator on Telegram (best-effort, never blocks the response)
    notify.send_telegram_async(notify.format_new_feedback({
        "name": name, "contact": contact, "message": message,
        "submitted_at": submitted_at, "ip": ip,
    }))

    return redirect(url_for("feedback.feedback_thanks"))


@bp.route("/feedback/thanks")
def feedback_thanks():
    return render_template("feedback_thanks.html")


# ---------------------------------------------------- admin
@bp.route("/admin/feedback")
def admin_feedback():
    if not _admin_authorised():
        abort(404)                       # do NOT leak that the endpoint exists
    show_spam = request.args.get("spam") == "1"
    with db.connect() as conn:
        if show_spam:
            rows = conn.execute("SELECT * FROM feedback ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM feedback WHERE is_spam=0 ORDER BY id DESC").fetchall()
        counts = conn.execute(
            "SELECT SUM(CASE WHEN is_spam=0 THEN 1 ELSE 0 END) AS ok, "
            "       SUM(CASE WHEN is_spam=1 THEN 1 ELSE 0 END) AS spam, "
            "       COUNT(*) AS total FROM feedback"
        ).fetchone()
    return render_template("admin_feedback.html",
                            rows=rows, counts=counts, show_spam=show_spam,
                            token=request.args.get("key", ""))


@bp.route("/admin/feedback/export")
def admin_feedback_export():
    if not _admin_authorised():
        abort(404)
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM feedback ORDER BY id").fetchall()
    payload = [dict(r) for r in rows]
    resp = make_response(json.dumps(payload, ensure_ascii=False, indent=2))
    resp.headers["Content-Type"]        = "application/json; charset=utf-8"
    resp.headers["Content-Disposition"] = (
        f"attachment; filename=feedback-{datetime.now():%Y%m%d-%H%M%S}.json"
    )
    return resp


@bp.route("/admin/feedback/<int:fid>/spam", methods=["POST"])
def admin_feedback_mark_spam(fid: int):
    if not _admin_authorised():
        abort(404)
    flag = 0 if request.form.get("undo") == "1" else 1
    with db.cursor() as conn:
        conn.execute("UPDATE feedback SET is_spam=? WHERE id=?", (flag, fid))
    return redirect(url_for("feedback.admin_feedback",
                             key=request.args.get("key", ""),
                             spam=request.args.get("spam", "")))


@bp.route("/admin/feedback/<int:fid>/delete", methods=["POST"])
def admin_feedback_delete(fid: int):
    if not _admin_authorised():
        abort(404)
    with db.cursor() as conn:
        conn.execute("DELETE FROM feedback WHERE id=?", (fid,))
    return redirect(url_for("feedback.admin_feedback",
                             key=request.args.get("key", ""),
                             spam=request.args.get("spam", "")))
