"""Set event stock once, with a database backup and recorded stock adjustments."""
import argparse
import json
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flask import Flask
from pos import db as pos_db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quantity", type=int, default=99)
    parser.add_argument("--event", default="convention-2026-10-15")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.quantity < 0:
        parser.error("Quantity must be nonnegative")
    if args.apply:
        archive = ROOT / "logs/archive" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_before-stock")
        archive.mkdir(parents=True)
        with closing(sqlite3.connect(pos_db.DB_PATH)) as source, closing(sqlite3.connect(archive / "mendo_pos.db")) as backup:
            source.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity check failed")
    app = Flask(__name__)
    with app.app_context():
        try:
            if args.apply:
                pos_db.init_db()
            items = pos_db.list_inventory(active_only=True)
            if any(int(item.get("reserved_quantity") or 0) > args.quantity for item in items):
                raise RuntimeError("Requested stock would be below an active reservation")
            changes = []
            for item in items:
                changes.append({"brand": item["brand"], "before": item["stock_quantity"], "after": args.quantity, "hardware_slot": item["hardware_slot"]})
                if args.apply and item["stock_quantity"] != args.quantity:
                    pos_db.update_stock(item["id"], args.quantity, "adjustment", reference=f"{args.event}: requested event stock setup")
            result = {"applied": args.apply, "changes": changes}
            if args.apply:
                result["backup"] = str(archive)
                (archive / "stock-setup.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
            print(json.dumps(result, indent=2))
        finally:
            pos_db.close_db()


if __name__ == "__main__":
    main()
