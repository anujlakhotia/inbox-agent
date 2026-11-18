"""One-off backfill of older mail: python -m app.backfill [days]   (default 30)

Fetches Gmail in batches of 100, triaging each batch with Claude, until nothing new is left in the window.
Safe to stop and re-run: stored emails are skipped.
"""
from __future__ import annotations

import sys

from .main import sync_now  # also loads .env
from . import db


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    db.init()
    total = 0
    while True:
        r = sync_now(days=days, limit=100)
        print(r, flush=True)
        total += r.get("fetched", 0)
        if r.get("status") != "ok" or r.get("fetched", 0) == 0:
            break
    print(f"done: {total} emails added" + ("" if r.get("status") == "ok" else f" (stopped: {r.get('status')}; re-run to continue)"))


if __name__ == "__main__":
    main()
