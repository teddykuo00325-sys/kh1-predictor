"""Notification helpers — Telegram (and easy to extend to Discord etc).

Telegram setup
--------------
1. Open https://t.me/BotFather on Telegram → /newbot → name + username.
2. Copy the HTTP API token (looks like 7891234:AAxxxxxxxxxxxxxxxxxxxxx).
3. Send /start to your new bot once (so it can DM you later).
4. Open https://t.me/userinfobot → /start → it tells you your numeric chat id.
5. Set two env vars on Render:
       TG_BOT_TOKEN   = <token from step 2>
       TG_CHAT_ID     = <chat id from step 4>

If either env var is missing, send_telegram() is a silent no-op so production
keeps working even without TG configured.
"""
from __future__ import annotations

import os
import sys
import textwrap
import urllib.parse

import requests


TELEGRAM_API = "https://api.telegram.org"
TIMEOUT_SECONDS = 8


def configured() -> bool:
    """True if both env vars are populated."""
    return bool(os.environ.get("TG_BOT_TOKEN", "").strip()
                 and os.environ.get("TG_CHAT_ID", "").strip())


def send_telegram(text: str, *, parse_mode: str = "HTML",
                   disable_web_page_preview: bool = True) -> tuple[bool, str]:
    """Send a message to TG_CHAT_ID using TG_BOT_TOKEN.

    Returns (ok, info) — info is the API response body on success or the
    error reason on failure.  Never raises so production stays alive.
    """
    token   = os.environ.get("TG_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TG_CHAT_ID",   "").strip()
    if not token or not chat_id:
        return False, "TG_BOT_TOKEN or TG_CHAT_ID not set"

    try:
        r = requests.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text":    text[:4000],
                "parse_mode": parse_mode,
                "disable_web_page_preview": "true" if disable_web_page_preview else "false",
            },
            timeout=TIMEOUT_SECONDS,
        )
        if r.status_code == 200:
            return True, r.text[:240]
        return False, f"HTTP {r.status_code}: {r.text[:240]}"
    except Exception as e:
        msg = f"{e.__class__.__name__}: {e}"
        print(f"[notify] telegram send failed: {msg}", file=sys.stderr)
        return False, msg


def send_telegram_async(text: str) -> None:
    """Currently runs synchronously (renamed for callers' expectations).

    A previous version used a daemon thread, but gunicorn's request-thread
    reaper kills daemon threads as soon as the worker goes idle, dropping
    Telegram messages.  ≤8 sec extra latency on /feedback POST is acceptable
    in exchange for guaranteed delivery.
    """
    send_telegram(text)


def html_escape(s: str | None) -> str:
    if not s:
        return ""
    return (s.replace("&", "&amp;").replace("<", "&lt;")
              .replace(">", "&gt;").replace('"', "&quot;"))


def format_new_feedback(feedback: dict, site_origin: str | None = None) -> str:
    """Build the Telegram message body for one new feedback row."""
    name    = html_escape(feedback.get("name")    or "匿名")
    contact = html_escape(feedback.get("contact") or "")
    message = html_escape(feedback.get("message") or "")
    submitted = html_escape(feedback.get("submitted_at") or "")
    ip      = html_escape(feedback.get("ip") or "")

    contact_line = f"\n聯絡：<code>{contact}</code>" if contact else ""
    origin = site_origin or os.environ.get("SITE_ORIGIN", "https://kh1-predictor.onrender.com")
    admin_url = f"{origin}/admin/feedback?key=" + urllib.parse.quote(
        os.environ.get("ADMIN_TOKEN", ""))
    # truncate long messages for the preview
    snippet = textwrap.shorten(message, width=600, placeholder="…")

    return (
        "📮 <b>新意見回饋</b>\n"
        f"暱稱：<b>{name}</b>"
        f"{contact_line}\n"
        f"時間：{submitted}  ｜ IP: <code>{ip}</code>\n"
        f"\n{snippet}\n"
        f'\n<a href="{admin_url}">→ 進入後台</a>'
    )
