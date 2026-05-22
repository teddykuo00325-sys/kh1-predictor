"""One-shot entry point: scrape -> extract -> serve."""
from __future__ import annotations

import argparse
import sys
import webbrowser
from threading import Timer

from src import app as app_mod
from src import extractor, scraper


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-scrape", action="store_true", help="don't re-scrape, use existing DB")
    ap.add_argument("--skip-extract", action="store_true", help="don't re-extract activities")
    ap.add_argument("--full", action="store_true", help="force full re-scrape")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if not args.skip_scrape:
        try:
            scraper.run(full=args.full)
        except Exception as e:
            print(f"[warn] scrape failed: {e}", file=sys.stderr)

    if not args.skip_extract:
        extractor.run()

    if not args.no_browser:
        Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    print("\nDashboard: http://127.0.0.1:5000  (Ctrl-C to stop)")
    app_mod.app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
