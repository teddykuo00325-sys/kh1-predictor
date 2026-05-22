"""Scrape kh1.uj.com.tw news list + article HTML into SQLite.

AJAX endpoint:    https://kh1.uj.com.tw/news/ajax/ajax_news_list.php?pn=<page>&c=<cat>&k=
Single article:   https://kh1.uj.com.tw/news/news.php?news=<id>&c=<cat>

Categories
  c=1 重要 (important)
  c=2 活動 (events / version updates)
  c=3 系統維護 (skipped by default — pure maintenance noise)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from . import db

BASE = "https://kh1.uj.com.tw/news"
LIST_URL = f"{BASE}/ajax/ajax_news_list.php"
ARTICLE_URL = f"{BASE}/news.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE}/news_list.php",
    "X-Requested-With": "XMLHttpRequest",
}

DEFAULT_CATEGORIES = (1, 2)        # skip 3 (maintenance) — useless for prediction
EARLIEST_YEAR = 2023               # cut-off as requested
SLEEP_SEC = 0.4                    # be polite to the server


# ------------------------------------------------------------------ helpers
def _get(url: str, params: dict | None = None, retries: int = 3) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url} params={params}: {last_err}")


def _parse_list_html(html_fragment: str) -> list[dict]:
    """Parse the .aResult HTML chunk returned by ajax_news_list.php."""
    soup = BeautifulSoup(html_fragment, "lxml")
    items: list[dict] = []
    for box in soup.select("div.newsbox01"):
        a = box.select_one("div.news a")
        date_div = box.select_one("div.datebox")
        if not a or not date_div:
            continue
        href = a.get("href", "")
        m = re.search(r"news=(\d+)&c=(\d+)", href)
        if not m:
            continue
        news_id = int(m.group(1))
        cat = int(m.group(2))
        title = a.get_text(strip=True)
        date_str = date_div.get_text(strip=True).replace(".", "-")
        items.append({"id": news_id, "category": cat, "title": title, "date": date_str})
    return items


def fetch_list_page(category: int, page: int) -> list[dict]:
    raw = _get(LIST_URL, params={"pn": page, "c": category, "k": ""})
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # site sometimes returns BOM or trailing junk
        data = json.loads(raw.strip().lstrip("﻿"))
    return _parse_list_html(data.get("aResult", ""))


def crawl_listing(categories=DEFAULT_CATEGORIES, max_pages: int = 60) -> list[dict]:
    """Walk every page of each category until we reach articles older than EARLIEST_YEAR."""
    seen: dict[int, dict] = {}
    for cat in categories:
        print(f"[list] category c={cat}")
        for page in range(1, max_pages + 1):
            items = fetch_list_page(cat, page)
            if not items:
                print(f"  page {page}: empty -> stop category")
                break
            oldest_year = min(int(it["date"][:4]) for it in items)
            new_count = 0
            for it in items:
                if int(it["date"][:4]) < EARLIEST_YEAR:
                    continue
                if it["id"] not in seen:
                    seen[it["id"]] = it
                    new_count += 1
            print(f"  page {page}: {len(items)} items, kept {new_count}, oldest {oldest_year}")
            time.sleep(SLEEP_SEC)
            if oldest_year < EARLIEST_YEAR:
                print(f"  reached cut-off ({EARLIEST_YEAR}) -> stop category")
                break
    return list(seen.values())


# ---------------------------------------------------- article (full HTML)
TITLE_SEL = "div.newsinfobox div.news"
DATE_SEL  = "div.newsinfobox div.datebox"
CONTENT_SEL = "div.newstxt"


def fetch_article(news_id: int, category: int) -> dict:
    html = _get(ARTICLE_URL, params={"news": news_id, "c": category})
    soup = BeautifulSoup(html, "lxml")
    title = (soup.select_one(TITLE_SEL) or soup.select_one("title"))
    title = title.get_text(strip=True) if title else f"article-{news_id}"
    date_el = soup.select_one(DATE_SEL)
    date_str = date_el.get_text(strip=True).replace(".", "-") if date_el else ""
    content_el = soup.select_one(CONTENT_SEL)
    content_html = str(content_el) if content_el else ""
    return {"title": title, "date": date_str, "html": html, "content_html": content_html}


def save_article(item: dict, content_html: str, html_blob: str) -> Path:
    """Write raw HTML to disk and insert/update DB row."""
    date_for_dir = item["date"].replace("-", "")[:6]  # YYYYMM
    out_dir = db.RAW_DIR / date_for_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{item['id']}.html"
    out_path.write_text(html_blob, encoding="utf-8")

    with db.cursor() as conn:
        conn.execute(
            """INSERT INTO articles (id, category, title, publish_date, url, html_path, fetched_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title,
                 publish_date=excluded.publish_date,
                 html_path=excluded.html_path,
                 fetched_at=excluded.fetched_at""",
            (
                item["id"],
                item["category"],
                item["title"],
                item["date"],
                f"{ARTICLE_URL}?news={item['id']}&c={item['category']}",
                str(out_path.relative_to(db.ROOT)),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
    return out_path


def existing_ids() -> set[int]:
    with db.connect() as conn:
        rows = conn.execute("SELECT id FROM articles").fetchall()
    return {r["id"] for r in rows}


def run(full: bool = False) -> None:
    db.init_schema()
    listing = crawl_listing()
    print(f"[list] total items >= {EARLIEST_YEAR}: {len(listing)}")

    already = set() if full else existing_ids()
    todo = [it for it in listing if it["id"] not in already]
    print(f"[fetch] {len(todo)} new / {len(listing) - len(todo)} cached")

    for i, item in enumerate(todo, 1):
        try:
            art = fetch_article(item["id"], item["category"])
            save_article(item, art["content_html"], art["html"])
            print(f"  [{i}/{len(todo)}] #{item['id']} {item['date']} {item['title'][:40]}")
        except Exception as e:
            print(f"  ! failed #{item['id']}: {e}", file=sys.stderr)
        time.sleep(SLEEP_SEC)

    db.set_state("last_scrape", datetime.now().isoformat(timespec="seconds"))
    print("[done] scrape finished")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="re-fetch every article ignoring cache")
    args = ap.parse_args()
    run(full=args.full)


if __name__ == "__main__":
    main()
