"""Verify event preparation preserves history in backup and leaves commerce intact."""

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from tools.prepare_event_logs import prepare


class EventPreparationTests(unittest.TestCase):
    def test_preview_then_reset_preserves_backup_and_commerce(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            database = root / "data" / "mendo_pos.db"
            with closing(sqlite3.connect(database)) as conn:
                conn.executescript("""
                    CREATE TABLE interaction_logs(id INTEGER PRIMARY KEY, text TEXT);
                    CREATE TABLE interaction_reviews(id INTEGER, interaction_id INTEGER REFERENCES interaction_logs(id));
                    CREATE TABLE interaction_adjudications(id INTEGER, interaction_id INTEGER REFERENCES interaction_logs(id));
                    CREATE TABLE operational_counters(count INTEGER);
                    CREATE TABLE inventory(id INTEGER, stock INTEGER);
                    CREATE TABLE transactions(id INTEGER, total INTEGER);
                    INSERT INTO interaction_logs VALUES(1, 'old consultation');
                    INSERT INTO interaction_reviews VALUES(1, 1);
                    INSERT INTO interaction_adjudications VALUES(1, 1);
                    INSERT INTO operational_counters VALUES(5);
                    INSERT INTO inventory VALUES(1, 17);
                    INSERT INTO transactions VALUES(1, 50);
                """)
            (root / "logs" / "mendo.log").write_text("old runtime evidence")
            (root / "logs" / "interactions.jsonl").write_text('{"legacy": true}\n')
            self.assertTrue(prepare(root, "convention")['dry_run'])
            self.assertEqual((root / "logs" / "mendo.log").read_text(), "old runtime evidence")
            result = prepare(root, "convention", apply=True)
            archive = Path(result['archive'])
            self.assertEqual((archive / "mendo.log").read_text(), "old runtime evidence")
            self.assertTrue((archive / "interactions.jsonl").exists())
            with closing(sqlite3.connect(archive / "mendo_pos.db")) as conn:
                self.assertEqual(conn.execute("SELECT text FROM interaction_logs").fetchone()[0], "old consultation")
            with closing(sqlite3.connect(database)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM interaction_logs").fetchone()[0], 0)
                self.assertEqual(conn.execute("SELECT stock FROM inventory").fetchone()[0], 17)
                self.assertEqual(conn.execute("SELECT total FROM transactions").fetchone()[0], 50)
            manifest = json.loads((archive / "manifest.json").read_text())
            self.assertIn("mendo_pos.db", manifest['archive_sha256'])
            self.assertEqual(manifest['after']['interaction_reviews'], 0)

    def test_rejects_path_as_event_name(self):
        with self.assertRaises(ValueError):
            prepare(Path("."), "../outside", apply=True)

    def test_failure_rolls_back_audit_and_restores_runtime_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "logs").mkdir()
            database = root / "data" / "mendo_pos.db"
            with closing(sqlite3.connect(database)) as conn:
                conn.executescript("CREATE TABLE interaction_logs(id INTEGER); INSERT INTO interaction_logs VALUES(1);")
            runtime = root / "logs" / "mendo.log"
            runtime.write_text("evidence before failure")
            with patch("tools.prepare_event_logs.checksum", side_effect=RuntimeError("simulated failure")):
                with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                    prepare(root, "convention", apply=True)
            self.assertEqual(runtime.read_text(), "evidence before failure")
            with closing(sqlite3.connect(database)) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM interaction_logs").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
