"""Import the official game database at kh1-web.uj.com.tw/gamedata into SQLite.

Unlike the news site, this one needs no HTML parsing: it is a static site whose
data ships as `window.<NAME>={...}` JavaScript assignments, so each file is one
`json.loads` away from a dict.

    data/meta.js    分類統計、地圖 ID、build_date (資料版本)
    data/items.js   9,583 件物品 — 數值、取得來源，福袋還附官方機率表
    data/sets.js    331 組套裝效果

`build_date` doubles as the cache key: the site serves every file with
`?v=YYYYMMDD` matching it, so when it hasn't moved there is nothing new to
fetch.  Run with --force to re-import anyway.

What we keep is the 福袋 probability tables — 437 of the 709 福袋 publish one,
and they are the thing this project otherwise has to enter by hand (see
`lootbox_data.py`).  Items are kept too so a pool entry can be resolved to a
real item; enemies and maps are left on the server until something needs them.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

import requests

from . import db

BASE = "https://kh1-web.uj.com.tw/gamedata"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE}/",
}
TIMEOUT = 180

DB_PATH = db.DATA_DIR / "gamedata.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS gd_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS gd_items (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    cat       TEXT,
    sub       TEXT,
    lv        INTEGER,
    descr     TEXT,
    stats     TEXT,          -- JSON [[label, value], …]
    flags     TEXT           -- JSON [str, …]
);
CREATE INDEX IF NOT EXISTS idx_gd_items_name ON gd_items(name);
CREATE INDEX IF NOT EXISTS idx_gd_items_cat  ON gd_items(cat);

-- One row per 福袋 that publishes its contents.
CREATE TABLE IF NOT EXISTS gd_lootbox (
    item_id    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    optional   INTEGER NOT NULL DEFAULT 0,   -- 自選 (pick one) rather than random
    pool_count INTEGER NOT NULL DEFAULT 0,
    fixed_count INTEGER NOT NULL DEFAULT 0,
    prob_sum   REAL,                          -- should be ~100; off means a gap
    FOREIGN KEY (item_id) REFERENCES gd_items(id)
);

-- The random pool: one row per possible reward.
CREATE TABLE IF NOT EXISTS gd_lootbox_pool (
    box_id      INTEGER NOT NULL,
    seq         INTEGER NOT NULL,
    reward_name TEXT NOT NULL,
    reward_id   INTEGER,                      -- null for 金錢 and other non-items
    prob        REAL,                         -- percent, as published
    prob_max    REAL,                         -- upper bound when it is a range
    PRIMARY KEY (box_id, seq),
    FOREIGN KEY (box_id) REFERENCES gd_lootbox(item_id)
);
CREATE INDEX IF NOT EXISTS idx_gd_pool_reward ON gd_lootbox_pool(reward_name);

-- Guaranteed contents, handed out on top of the random pull.
CREATE TABLE IF NOT EXISTS gd_lootbox_fixed (
    box_id      INTEGER NOT NULL,
    seq         INTEGER NOT NULL,
    reward_name TEXT NOT NULL,
    reward_id   INTEGER,
    qty         INTEGER,
    PRIMARY KEY (box_id, seq),
    FOREIGN KEY (box_id) REFERENCES gd_lootbox(item_id)
);
"""


# ------------------------------------------------------------------ db
def connect() -> sqlite3.Connection:
    db.ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_meta(key: str, default: str | None = None) -> str | None:
    if not DB_PATH.exists():
        return default
    try:
        with connect() as conn:
            row = conn.execute("SELECT value FROM gd_meta WHERE key=?", (key,)).fetchone()
    except sqlite3.OperationalError:       # table not created yet
        return default
    return row["value"] if row else default


# ------------------------------------------------------------------ fetch
ERROR_PATH = db.DATA_DIR / "gamedata_error.txt"


def last_error() -> str | None:
    """Why the last import failed, for the page to show instead of a bare blank."""
    try:
        return ERROR_PATH.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _fetch_js(name: str, version: str | None) -> dict | list:
    """GET data/<name>.js and unwrap its `window.X = <json>;` assignment.

    items.js is 7.5MB, and the free Render instance has 512MB, so this streams
    to disk and decodes from an offset rather than slicing: holding the response
    body, `.text` and a sliced copy at once would be three copies of it.
    """
    url = f"{BASE}/data/{name}.js"
    tmp = db.DATA_DIR / f".gamedata_{name}.tmp"
    db.ensure_dirs()
    with requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True,
                       params={"v": version} if version else None) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
    try:
        text = tmp.read_text(encoding="utf-8")
        # raw_decode reads from an index and ignores the trailing ";"
        obj, _ = json.JSONDecoder().raw_decode(text, text.index("=") + 1)
        return obj
    finally:
        del text
        tmp.unlink(missing_ok=True)


def _num(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ import
def _store_meta(conn, meta: dict) -> None:
    rows = [("build_date", meta.get("build_date", ""))]
    # counts are small and handy for the UI; the rest of meta stays on the site
    for k in ("items", "enemies", "maps"):
        if k in meta:
            rows.append((f"count_{k}", str(meta[k])))
    rows.append(("items_cat", json.dumps(meta.get("items_cat", {}), ensure_ascii=False)))
    conn.executemany(
        "INSERT INTO gd_meta(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value", rows)


def _store_items(conn, items: list[dict]) -> tuple[int, int, int]:
    conn.execute("DELETE FROM gd_lootbox_pool")
    conn.execute("DELETE FROM gd_lootbox_fixed")
    conn.execute("DELETE FROM gd_lootbox")
    conn.execute("DELETE FROM gd_items")

    n_items = n_boxes = n_pool = 0
    for it in items:
        conn.execute(
            """INSERT INTO gd_items(id,name,cat,sub,lv,descr,stats,flags)
               VALUES(?,?,?,?,?,?,?,?)""",
            (it["id"], it["name"], it.get("cat"), it.get("sub"), it.get("lv"),
             it.get("desc"),
             json.dumps(it.get("stats", []), ensure_ascii=False),
             json.dumps(it.get("flags", []), ensure_ascii=False)))
        n_items += 1

        contents = it.get("contents") or {}
        pool, fixed = contents.get("pool") or [], contents.get("fixed") or []
        if not pool and not fixed:
            continue

        prob_sum = sum(p for p in (_num(e[2]) for e in pool
                                    if len(e) > 2) if p is not None) or None
        conn.execute(
            """INSERT INTO gd_lootbox(item_id,name,optional,pool_count,fixed_count,prob_sum)
               VALUES(?,?,?,?,?,?)""",
            (it["id"], it["name"], int(bool(contents.get("optional"))),
             len(pool), len(fixed), prob_sum))
        n_boxes += 1

        for seq, e in enumerate(pool):
            # [name, item_id, prob, prob_max] — the last two are equal unless
            # the drop is published as a range.
            conn.execute(
                """INSERT INTO gd_lootbox_pool(box_id,seq,reward_name,reward_id,prob,prob_max)
                   VALUES(?,?,?,?,?,?)""",
                (it["id"], seq, e[0], e[1] if len(e) > 1 else None,
                 _num(e[2]) if len(e) > 2 else None,
                 _num(e[3]) if len(e) > 3 else None))
            n_pool += 1
        for seq, e in enumerate(fixed):
            conn.execute(
                """INSERT INTO gd_lootbox_fixed(box_id,seq,reward_name,reward_id,qty)
                   VALUES(?,?,?,?,?)""",
                (it["id"], seq, e[0], e[1] if len(e) > 1 else None,
                 int(_num(e[2]) or 1) if len(e) > 2 else None))
    return n_items, n_boxes, n_pool


def run(force: bool = False) -> None:
    init_schema()
    meta = _fetch_js("meta", None)
    build_date = meta.get("build_date", "")
    local = get_meta("build_date")
    print(f"[gamedata] remote build_date={build_date or '?'}  local={local or '(none)'}")
    if local and local == build_date and not force:
        print("[gamedata] already current -> skip  (use --force to re-import)")
        return

    print(f"[gamedata] fetching items.js (~7.5MB) ...")
    items = _fetch_js("items", build_date.replace("-", "") or None)
    print(f"[gamedata] parsed {len(items)} items")

    with cursor() as conn:
        n_items, n_boxes, n_pool = _store_items(conn, items)
        _store_meta(conn, meta)
    print(f"[gamedata] stored items={n_items}  福袋={n_boxes}  獎品條目={n_pool}")
    print("[gamedata] done")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                     help="re-import even when build_date hasn't changed")
    args = ap.parse_args()
    try:
        run(force=args.force)
        ERROR_PATH.unlink(missing_ok=True)
    except Exception as e:
        # The news data is the project's core, so a gamedata problem must not
        # fail the Render build — but it must not vanish either, or the page
        # just says "not imported" with no way to tell why from outside.
        reason = f"{type(e).__name__}: {e}"
        print(f"[gamedata] FAILED -> {reason}", file=sys.stderr)
        print("[gamedata] site will fall back to showing this reason", file=sys.stderr)
        try:
            db.ensure_dirs()
            ERROR_PATH.write_text(reason[:500], encoding="utf-8")
        except OSError:
            pass


if __name__ == "__main__":
    main()


# ------------------------------------------------------------------ queries
def available() -> bool:
    """False when the import has not run — pages fall back instead of erroring."""
    return get_meta("build_date") is not None


def build_date() -> str | None:
    return get_meta("build_date")


def search_boxes(q: str = "", limit: int = 60) -> list[dict]:
    """福袋 whose own name matches `q`, or that can drop a reward matching it.

    Searching by reward is the useful direction in practice — "which 福袋 can
    give me 轉生石" is the question, not "what is in this box".
    """
    if not available():
        return []
    sql = """SELECT b.*, i.cat, i.sub
             FROM gd_lootbox b JOIN gd_items i ON i.id = b.item_id"""
    params: list = []
    if q:
        sql += """ WHERE b.name LIKE ?
                   OR EXISTS (SELECT 1 FROM gd_lootbox_pool p
                              WHERE p.box_id = b.item_id AND p.reward_name LIKE ?)
                   OR EXISTS (SELECT 1 FROM gd_lootbox_fixed f
                              WHERE f.box_id = b.item_id AND f.reward_name LIKE ?)"""
        params += [f"%{q}%"] * 3
    sql += " ORDER BY b.pool_count DESC, b.name LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params)]


def box_contents(box_id: int) -> dict:
    """One 福袋 with its pool sorted by probability, rarest last."""
    if not available():
        return {}
    with connect() as conn:
        box = conn.execute("SELECT * FROM gd_lootbox WHERE item_id=?", (box_id,)).fetchone()
        if not box:
            return {}
        pool = conn.execute(
            "SELECT * FROM gd_lootbox_pool WHERE box_id=? ORDER BY prob DESC, seq",
            (box_id,)).fetchall()
        fixed = conn.execute(
            "SELECT * FROM gd_lootbox_fixed WHERE box_id=? ORDER BY seq", (box_id,)).fetchall()
    return {"box": dict(box), "pool": [dict(r) for r in pool],
            "fixed": [dict(r) for r in fixed]}


def passthrough_target(box_id: int) -> dict | None:
    """If `box_id` is a wrapper — one reward at 100%, nothing fixed — return it.

    The game wraps prizes a lot: 士兵體力進階福袋 drops a 士兵體力進階錦囊 at 1%,
    and that 錦囊 opens into the 士兵體力進階之書 every time.  For anyone working
    out odds the two steps are one 1% chance at the book, so a comparison that
    stops at the 錦囊 reports a difference that does not exist.
    """
    data = box_contents(box_id)
    if not data or data["box"]["fixed_count"] or len(data["pool"]) != 1:
        return None
    only = data["pool"][0]
    return only if (only["prob"] or 0) >= 100 else None


def official_pool(box_id: int, resolve_passthrough: bool = True) -> dict[str, float]:
    """{reward name: probability as a 0-1 fraction} — the shape `lootbox_data` uses.

    With `resolve_passthrough`, a reward that is itself a 100% wrapper is
    reported as what it actually yields.  Only one level is followed; deeper
    nesting is rare and chasing it risks a cycle.
    """
    data = box_contents(box_id)
    out: dict[str, float] = {}
    for r in data.get("pool", []):
        name, prob = r["reward_name"], (r["prob"] or 0) / 100
        if resolve_passthrough and r["reward_id"]:
            inner = passthrough_target(r["reward_id"])
            if inner:
                name = inner["reward_name"]
        out[name] = out.get(name, 0) + prob
    return out
