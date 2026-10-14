"""Archive old evidence and start an empty consultation audit (app must be stopped)."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_TABLES = (
    "interaction_reviews", "interaction_adjudications",
    "interaction_logs", "operational_counters",
)


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {
        name: conn.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0]
        for (name,) in names
    }


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare(root: Path, event: str, apply: bool = False) -> dict:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", event):
        raise ValueError("Event must be a short name using letters, numbers, underscores or hyphens")
    database = root / "data" / "mendo_pos.db"
    if not database.is_file():
        raise FileNotFoundError(database)
    log_dir = root / "logs"
    files = sorted({*log_dir.glob("*.log"), *log_dir.glob("mendo.log*"), *log_dir.glob("*.jsonl")})
    with closing(sqlite3.connect(database)) as conn:
        before = table_counts(conn)
    report = {"event": event, "before": before, "runtime_files": [p.name for p in files]}
    if not apply:
        return {**report, "dry_run": True}

    now = datetime.now(timezone.utc)
    archive = log_dir / "archive" / (now.strftime("%Y%m%dT%H%M%S%fZ") + "_" + event)
    archive.mkdir(parents=True, exist_ok=False)
    # Hold the write lock throughout backup and reset. A separate reader takes a
    # WAL-aware snapshot while no other connection can change the database.
    conn = sqlite3.connect(database, timeout=5)
    conn.execute("PRAGMA foreign_keys=ON")
    moved = []
    try:
        conn.execute("BEGIN IMMEDIATE")
        before = table_counts(conn)
        report["before"] = before
        with closing(sqlite3.connect(database)) as source, closing(sqlite3.connect(archive / "mendo_pos.db")) as backup:
            source.backup(backup)
            if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Database backup failed integrity check")
            if table_counts(backup) != before:
                raise RuntimeError("Database backup counts differ from live database")
        for path in files:
            if path.is_file():
                shutil.copy2(path, archive / path.name)
        # Rename instead of truncating: on Windows, an open logging handler
        # prevents this and aborts the reset. On all platforms stop the app first.
        for path in files:
            if path.is_file():
                path.replace(archive / path.name)
                moved.append(path)
        for name in AUDIT_TABLES:
            if name in before:
                conn.execute(f'DELETE FROM "{name}"')
        after = table_counts(conn)
        for name, count in before.items():
            expected = 0 if name in AUDIT_TABLES else count
            if after[name] != expected:
                raise RuntimeError(f"Unexpected count after reset: {name}")
        try:
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True,
            ).stdout.strip()
            status = subprocess.run(
                ["git", "status", "--short"], cwd=root, capture_output=True, text=True, check=True,
            ).stdout.splitlines()
        except (OSError, subprocess.CalledProcessError):
            revision, status = None, []
        source_files = [
            p for folder in ("mendo_core", "pos", "web", "hardware")
            for p in sorted((root / folder).rglob("*"))
            if p.is_file() and p.suffix in {".py", ".js", ".html", ".ino", ".css"}
        ]
        for relative in ("app.py", "wsgi.py", "requirements.txt", "data/Mendo-Datasets.json"):
            if (root / relative).is_file():
                source_files.append(root / relative)
        for path in source_files:
            target = archive / "source" / path.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        manifest = {
            **report, "prepared_at_utc": now.isoformat(), "after": after,
            "git_revision": revision, "git_status": status,
            "source_sha256": {
                str(p.relative_to(root)): checksum(p)
                for p in source_files
            },
            "archive_sha256": {p.name: checksum(p) for p in sorted(archive.iterdir()) if p.is_file()},
            "reset_tables": [name for name in AUDIT_TABLES if name in before],
            "consent_policy": "Unchanged: raw consultation audit requires research consent",
        }
        (archive / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        log_dir.mkdir(exist_ok=True)
        (log_dir / "mendo.log").write_text(
            f"{now.isoformat()} [INFO] mendo.event: Prepared {event}; archive={archive.name}\n",
            encoding="utf-8",
        )
        conn.commit()
    except Exception:
        conn.rollback()
        for path in moved:
            shutil.copy2(archive / path.name, path)
        raise
    finally:
        conn.close()
    return {"event": event, "archive": str(archive), "before": before, "after": after}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True)
    parser.add_argument("--apply", action="store_true", help="Back up and reset; stop app and hardware daemon first")
    args = parser.parse_args()
    print(json.dumps(prepare(ROOT, args.event, args.apply), indent=2))


if __name__ == "__main__":
    main()
