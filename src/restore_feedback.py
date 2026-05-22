"""Restore the feedback table from data/backups/feedback-latest.json.

Called during Render's build step AFTER scraper + extractor have populated
the news tables.  The fresh container's filesystem starts empty, so feedback
collected since the last weekly backup commit would be lost otherwise.

The JSON file is produced by the GitHub Actions workflow
`.github/workflows/weekly-update.yml` (and can also be downloaded manually
from `/admin/feedback/export?key=ADMIN_TOKEN`).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from . import db

BACKUP = Path(__file__).resolve().parent.parent / "data" / "backups" / "feedback-latest.json"


def main() -> int:
    db.init_schema()

    if not BACKUP.exists():
        print(f"[restore_feedback] no backup file at {BACKUP} — skipping (first deploy?)")
        return 0

    try:
        # utf-8-sig transparently strips a BOM if a Windows editor saved one.
        records = json.loads(BACKUP.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"[restore_feedback] couldn't parse backup ({e}) — skipping",
              file=sys.stderr)
        return 0

    if not isinstance(records, list) or not records:
        print(f"[restore_feedback] backup is empty list — nothing to restore")
        return 0

    inserted = 0
    with db.cursor() as conn:
        # Wipe whatever ended up in feedback during this build (should be empty,
        # but defensive in case anything wrote to it during scrape).
        conn.execute("DELETE FROM feedback")
        for r in records:
            try:
                conn.execute(
                    """INSERT INTO feedback
                       (id, name, contact, message, submitted_at, ip, user_agent, is_spam)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        r.get("id"),
                        r.get("name"),
                        r.get("contact"),
                        r["message"],
                        r["submitted_at"],
                        r.get("ip"),
                        r.get("user_agent"),
                        int(r.get("is_spam") or 0),
                    ),
                )
                inserted += 1
            except (KeyError, sqlite3.IntegrityError) as e:
                print(f"[restore_feedback] skipped one record: {e}", file=sys.stderr)

    print(f"[restore_feedback] restored {inserted} / {len(records)} feedback records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
