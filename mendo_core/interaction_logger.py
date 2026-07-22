"""Mendo Interaction Logger — records every consultation.

Each consultation interaction is saved to both SQLite (pos database) and JSONL
(as a fallback). The SQLite table enables structured querying, CSV export, and
avoids unbounded file growth.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("mendo.logger")

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "interactions.jsonl"
_DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "mendo_pos.db")

_disabled = False


def _ensure_log_dir():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_db() -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception as e:
        log.warning("Cannot open SQLite log db (%s), falling back to JSONL", e)
        return None


def _write_sqlite(entry: dict) -> bool:
    conn = _get_db()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        conn.execute(
            """INSERT OR IGNORE INTO interaction_logs
               (interaction_id, timestamp, session_id, interaction_type,
                user_input, extracted_symptoms, extraction_source, red_flags,
                pipeline_stages, action, recommendations, clarification,
                context_override, severity, age, pipeline_detail,
                recommendation_detail)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry["interaction_id"],
                entry["timestamp"],
                entry.get("session_id"),
                entry["interaction_type"],
                entry.get("user_input"),
                json.dumps(entry.get("extracted_symptoms", []), ensure_ascii=False),
                entry.get("extraction_source"),
                json.dumps(entry.get("red_flags", []), ensure_ascii=False),
                json.dumps(entry.get("pipeline_stages", []), ensure_ascii=False, default=str),
                entry.get("action"),
                json.dumps(entry.get("recommendations", []), ensure_ascii=False, default=str),
                entry.get("clarification"),
                entry.get("context_override"),
                entry.get("severity"),
                entry.get("age"),
                json.dumps(entry.get("pipeline_detail", {}), ensure_ascii=False, default=str),
                json.dumps(entry.get("recommendation_detail", {}), ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        log.error("SQLite log write failed: %s", e)
        return False
    finally:
        conn.close()


def _ensure_table(conn: sqlite3.Connection):
    conn.execute("""CREATE TABLE IF NOT EXISTS interaction_logs (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        interaction_id      TEXT    UNIQUE NOT NULL,
        timestamp           TEXT    NOT NULL,
        session_id          TEXT,
        interaction_type    TEXT    NOT NULL,
        user_input          TEXT,
        extracted_symptoms  TEXT    DEFAULT '[]',
        extraction_source   TEXT,
        red_flags           TEXT    DEFAULT '[]',
        pipeline_stages     TEXT    DEFAULT '[]',
        action              TEXT,
        recommendations     TEXT    DEFAULT '[]',
        clarification       TEXT,
        context_override    TEXT,
        severity            INTEGER,
        age                 INTEGER,
        pipeline_detail     TEXT    DEFAULT '{}',
        recommendation_detail TEXT  DEFAULT '{}',
        created_at          TEXT    DEFAULT (datetime('now','localtime'))
    )""")


def _write_jsonl(entry: dict):
    _ensure_log_dir()
    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        log.error("JSONL fallback write failed: %s", e)


def log_interaction(
    user_input: str,
    extracted_symptoms: List[str],
    extraction_source: str,
    pipeline_stages: Any,
    recommendation: Dict[str, Any],
    red_flags: Optional[List[str]] = None,
    clarification: Optional[str] = None,
    context_override: Optional[str] = None,
    interaction_type: str = "initial_analysis",
    severity: Optional[int] = None,
    age: Optional[int] = None,
    session_id: Optional[str] = None,
    headache_location: Optional[str] = None,
    headache_danger: Optional[str] = None,
    duration_symptom: Optional[str] = None,
    duration_value: Optional[str] = None,
    duration_days: Optional[int] = None,
) -> str:
    if _disabled:
        return "disabled"

    interaction_id = uuid.uuid4().hex[:12]

    rec_list = []
    action = recommendation.get("action", "unknown")
    if action == "recommend":
        for r in recommendation.get("recommendations", []):
            rec_list.append({
                "brand": r.get("brand", ""),
                "generic": r.get("active_ingredients", r.get("generic_name", r.get("generic", ""))),
                "category": r.get("drug_category"),
                "reasons": r.get("reasons"),
                "min_age": r.get("min_age"),
                "dosage_form": r.get("dosage_form"),
            })

    numbered_stages = []
    step_num = 1
    for stage in (pipeline_stages or []):
        stage_copy = dict(stage)
        stage_copy["step"] = step_num
        if stage.get("stage") == "semantic" and stage.get("scores"):
            stage_copy["scores"] = [
                {"symptom": s["symptom"], "score": round(s["score"], 4)}
                for s in stage["scores"]
            ]
        numbered_stages.append(stage_copy)
        step_num += 1

    entry = {
        "interaction_id": interaction_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id or uuid.uuid4().hex[:8],
        "interaction_type": interaction_type,
        "user_input": user_input,
        "extracted_symptoms": extracted_symptoms,
        "extraction_source": extraction_source,
        "red_flags": red_flags or [],
        "pipeline_stages": numbered_stages,
        "action": action,
        "recommendations": rec_list,
        "clarification": clarification,
        "context_override": context_override,
        "severity": severity,
        "age": age,
        "pipeline_detail": {
            "semantic_threshold": 0.65,
            "semantic_top_margin": 0.08,
            "semantic_max_symptoms": 2,
            "enable_semantic_fallback": True,
            "headache_location": headache_location,
            "headache_danger": headache_danger,
            "duration_symptom": duration_symptom,
            "duration_value": duration_value,
            "duration_days": duration_days,
        },
        "recommendation_detail": {
            "action": action,
            "clarification_question": recommendation.get("question"),
            "clarification_options": [
                {"label": o.get("label"), "value": o.get("value")}
                for o in (recommendation.get("options") or [])
            ] if recommendation.get("options") else None,
            "message": recommendation.get("message"),
        }
    }

    # Write to SQLite primary, JSONL as fallback
    if not _write_sqlite(entry):
        _write_jsonl(entry)

    log.info("Logged interaction %s (type=%s, %d symptoms, action=%s)",
             interaction_id, interaction_type, len(extracted_symptoms), action)

    return interaction_id


def get_interaction_logs(
    limit: int = 500, offset: int = 0, search: str = ""
) -> list[dict]:
    """Return parsed interaction logs as a list of dicts."""
    conn = _get_db()
    if conn is None:
        return []
    try:
        _ensure_table(conn)
        where = ""
        params: list = []
        if search:
            where = "WHERE user_input LIKE ? OR extracted_symptoms LIKE ? OR interaction_id LIKE ?"
            like = f"%{search}%"
            params = [like, like, like]
        rows = conn.execute(
            f"SELECT * FROM interaction_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for col in ("extracted_symptoms", "red_flags", "recommendations", "pipeline_stages"):
                try:
                    d[col] = json.loads(d[col]) if isinstance(d[col], str) else d[col]
                except (json.JSONDecodeError, TypeError):
                    d[col] = []
            try:
                d["pipeline_detail"] = json.loads(d["pipeline_detail"]) if isinstance(d["pipeline_detail"], str) else d["pipeline_detail"]
            except (json.JSONDecodeError, TypeError):
                d["pipeline_detail"] = {}
            try:
                d["recommendation_detail"] = json.loads(d["recommendation_detail"]) if isinstance(d["recommendation_detail"], str) else d["recommendation_detail"]
            except (json.JSONDecodeError, TypeError):
                d["recommendation_detail"] = {}
            result.append(d)
        return result
    except Exception as e:
        log.error("get_interaction_logs failed: %s", e)
        return []
    finally:
        conn.close()


def count_interaction_logs(search: str = "") -> int:
    """Count total logs (optionally filtered by search)."""
    conn = _get_db()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        if search:
            like = f"%{search}%"
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM interaction_logs WHERE user_input LIKE ? OR extracted_symptoms LIKE ?",
                (like, like),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM interaction_logs").fetchone()
        return row["c"] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def count_logs_today() -> int:
    """Count logs created today."""
    conn = _get_db()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM interaction_logs WHERE date(timestamp) = date('now','localtime')"
        ).fetchone()
        return row["c"] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def get_most_common_symptom() -> str:
    """Return the most frequently extracted symptom name."""
    conn = _get_db()
    if conn is None:
        return ""
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT extracted_symptoms FROM interaction_logs WHERE extracted_symptoms != '[]'"
        ).fetchall()
        from collections import Counter
        counter: Counter = Counter()
        for r in rows:
            try:
                syms = json.loads(r["extracted_symptoms"])
                if isinstance(syms, list):
                    counter.update(syms)
            except (json.JSONDecodeError, TypeError):
                pass
        if counter:
            return counter.most_common(1)[0][0]
        return ""
    except Exception:
        return ""
    finally:
        conn.close()


def export_logs_as_csv() -> str:
    """Return all interaction logs as a CSV string (header + rows)."""
    conn = _get_db()
    if conn is None:
        return ""
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT * FROM interaction_logs ORDER BY id"
        ).fetchall()

        import csv, io
        buf = io.StringIO()
        if rows:
            writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
            writer.writeheader()
            for r in rows:
                writer.writerow(dict(r))
        return buf.getvalue()
    except Exception as e:
        log.error("CSV export failed: %s", e)
        return ""
    finally:
        conn.close()


def export_logs_as_json() -> str:
    """Return all interaction logs as a JSON string (parsed arrays/objects)."""
    logs = get_interaction_logs(limit=999999)
    return json.dumps(logs, ensure_ascii=False, indent=2, default=str)


def export_logs_as_pdf() -> bytes:
    """Return all interaction logs as a PDF (bytes)."""
    conn = _get_db()
    if conn is None:
        return b""
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT * FROM interaction_logs ORDER BY id"
        ).fetchall()
        if not rows:
            return b""

        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Courier", size=6)

        # Header row — column names from first row
        cols = list(rows[0].keys())
        # Print header
        line = " | ".join(cols)
        # Split across pages if needed — use multi_cell
        pdf.set_font("Courier", style="B", size=6)
        pdf.cell(0, 4, "Mendo Interaction Logs", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Column widths: distribute page width (190mm) across cols
        col_widths = {}
        n = len(cols)
        if n > 0:
            w = max(10, min(50, 190 // n))
            for c in cols:
                col_widths[c] = w
            # Header
            pdf.set_font("Courier", style="B", size=5)
            for c in cols:
                pdf.cell(col_widths[c], 4, c[:col_widths[c]//2], border=1)
            pdf.ln()
            # Data
            pdf.set_font("Courier", size=5)
            for row in rows:
                r = dict(row)
                for c in cols:
                    val = str(r.get(c, ""))[:col_widths[c]//2]
                    pdf.cell(col_widths[c], 4, val, border=1)
                pdf.ln()
                # Check page break
                if pdf.get_y() > 270:
                    pdf.add_page()
                    pdf.set_font("Courier", style="B", size=5)
                    for c in cols:
                        pdf.cell(col_widths[c], 4, c[:col_widths[c]//2], border=1)
                    pdf.ln()
                    pdf.set_font("Courier", size=5)

        return pdf.output()
    except Exception as e:
        log.error("PDF export failed: %s", e)
        return b""
    finally:
        conn.close()
    conn = _get_db()
    if conn is None:
        return 0
    try:
        _ensure_table(conn)
        return conn.execute("SELECT COUNT(*) AS c FROM interaction_logs").fetchone()["c"]
    except Exception:
        return 0
    finally:
        conn.close()


def migrate_jsonl_to_sqlite() -> int:
    """Import existing JSONL entries into SQLite. Returns count imported."""
    jsonl_path = _LOG_DIR / "interactions.jsonl"
    if not jsonl_path.exists():
        return 0

    imported = 0
    conn = _get_db()
    if conn is None:
        return 0

    try:
        _ensure_table(conn)
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                conn.execute(
                    """INSERT OR IGNORE INTO interaction_logs
                       (interaction_id, timestamp, session_id, interaction_type,
                        user_input, extracted_symptoms, extraction_source, red_flags,
                        pipeline_stages, action, recommendations, clarification,
                        context_override, severity, age, pipeline_detail,
                        recommendation_detail)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        entry.get("interaction_id") or uuid.uuid4().hex[:12],
                        entry.get("timestamp", datetime.now().isoformat()),
                        entry.get("session_id"),
                        entry.get("interaction_type", "initial_analysis"),
                        entry.get("user_input"),
                        json.dumps(entry.get("extracted_symptoms", []), ensure_ascii=False),
                        entry.get("extraction_source"),
                        json.dumps(entry.get("red_flags", []), ensure_ascii=False),
                        json.dumps(entry.get("pipeline_stages", []), ensure_ascii=False, default=str),
                        entry.get("action"),
                        json.dumps(entry.get("recommendations", []), ensure_ascii=False, default=str),
                        entry.get("clarification"),
                        entry.get("context_override"),
                        entry.get("severity"),
                        entry.get("age"),
                        json.dumps(entry.get("pipeline_detail", {}), ensure_ascii=False, default=str),
                        json.dumps(entry.get("recommendation_detail", {}), ensure_ascii=False, default=str),
                    ),
                )
                imported += 1
            conn.commit()
        log.info("Migrated %d JSONL records to SQLite", imported)
    except Exception as e:
        log.error("JSONL migration failed: %s", e)
    finally:
        conn.close()

    return imported
