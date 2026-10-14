"""Save a WAL-aware database and local build snapshot without resetting evidence."""
import argparse
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def snapshot(event: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", event):
        raise ValueError("Use a short event name with letters, digits, hyphens or underscores")
    now = datetime.now(timezone.utc)
    archive = ROOT / "logs/archive" / (now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + event)
    archive.mkdir(parents=True)
    with closing(sqlite3.connect((ROOT / "data/mendo_pos.db").as_uri() + "?mode=ro", uri=True)) as source, closing(sqlite3.connect(archive / "mendo_pos.db")) as backup:
        source.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Snapshot integrity check failed")
    files = [
        path for folder in ("mendo_core", "pos", "web", "hardware")
        for path in (ROOT / folder).rglob("*")
        if path.is_file() and path.suffix in {".py", ".js", ".html", ".ino", ".css"}
    ]
    files += [ROOT / name for name in ("app.py", "wsgi.py", "requirements.txt", "data/Mendo-Datasets.json") if (ROOT / name).is_file()]
    files += list((ROOT / "web/static/images/medicines").glob("*"))
    for path in files:
        target = archive / "source" / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    for path in {*(ROOT / "logs").glob("*.log"), *(ROOT / "logs").glob("mendo.log.*")}:
        if path.is_file():
            shutil.copy2(path, archive / path.name)
    hashes = {str(path.relative_to(archive)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(archive.rglob("*")) if path.is_file()}
    (archive / "manifest.json").write_text(json.dumps({"event":event,"captured_at_utc":now.isoformat(),"reset":False,"sha256":hashes}, indent=2) + "\n", encoding="utf8")
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True)
    args = parser.parse_args()
    print(snapshot(args.event))
