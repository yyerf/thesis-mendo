"""Consent-aware consultation audit log and expert annotation store."""

from __future__ import annotations

import csv
import io
import json
import logging
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .evaluation import (
    aggregate_metrics,
    case_metrics,
    clinical_appropriateness_rate,
    multilabel_reviewer_kappa,
)
from .prediction_pipeline import ENGINE_ID, TRACE_SCHEMA_VERSION

log = logging.getLogger("mendo.logger")
_DB_PATH = str(Path(__file__).resolve().parents[1] / "data" / "mendo_pos.db")
CONSENT_VERSION = "research-consent-v1-2026-07"
_disabled = False

_JSON_COLUMNS = {
    "extracted_symptoms",
    "red_flags",
    "pipeline_stages",
    "recommendations",
    "pipeline_detail",
    "recommendation_detail",
}


def _get_db() -> Optional[sqlite3.Connection]:
    try:
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(conn)
        return conn
    except Exception as exc:
        log.error("Cannot open consultation audit database: %s", exc)
        return None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS interaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT UNIQUE NOT NULL,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            interaction_type TEXT NOT NULL,
            user_input TEXT,
            extracted_symptoms TEXT DEFAULT '[]',
            extraction_source TEXT,
            red_flags TEXT DEFAULT '[]',
            pipeline_stages TEXT DEFAULT '[]',
            action TEXT,
            recommendations TEXT DEFAULT '[]',
            clarification TEXT,
            context_override TEXT,
            severity INTEGER,
            age INTEGER,
            pipeline_detail TEXT DEFAULT '{}',
            recommendation_detail TEXT DEFAULT '{}',
            research_consent INTEGER NOT NULL DEFAULT 0,
            consent_version TEXT,
            language TEXT,
            input_mode TEXT,
            trace_version INTEGER NOT NULL DEFAULT 1,
            engine_id TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS operational_counters (
            counter_date TEXT NOT NULL,
            interaction_type TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(counter_date, interaction_type)
        );
        CREATE TABLE IF NOT EXISTS interaction_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            interaction_id TEXT NOT NULL,
            reviewer_id INTEGER NOT NULL,
            expected_symptoms TEXT NOT NULL DEFAULT '[]',
            correct_symptoms TEXT NOT NULL DEFAULT '[]',
            missed_symptoms TEXT NOT NULL DEFAULT '[]',
            expected_red_flags TEXT NOT NULL DEFAULT '[]',
            expected_action TEXT NOT NULL,
            recommendation_appropriateness TEXT NOT NULL,
            expected_medicines TEXT NOT NULL DEFAULT '[]',
            error_category TEXT,
            reviewer_confidence INTEGER NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(interaction_id, reviewer_id)
        );
        CREATE TABLE IF NOT EXISTS interaction_adjudications (
            interaction_id TEXT PRIMARY KEY,
            adjudicator_id INTEGER NOT NULL,
            final_symptoms TEXT NOT NULL DEFAULT '[]',
            final_red_flags TEXT NOT NULL DEFAULT '[]',
            final_action TEXT NOT NULL,
            recommendation_appropriateness TEXT NOT NULL,
            expected_medicines TEXT NOT NULL DEFAULT '[]',
            notes TEXT,
            adjudicated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        """
    )
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(interaction_logs)")
    }
    for name, definition in {
        "research_consent": "INTEGER NOT NULL DEFAULT 0",
        "consent_version": "TEXT",
        "language": "TEXT",
        "input_mode": "TEXT",
        "trace_version": "INTEGER NOT NULL DEFAULT 1",
        "engine_id": "TEXT",
    }.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE interaction_logs ADD COLUMN {name} {definition}")
    review_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(interaction_reviews)")
    }
    if "correct_symptoms" not in review_columns:
        conn.execute(
            "ALTER TABLE interaction_reviews "
            "ADD COLUMN correct_symptoms TEXT NOT NULL DEFAULT '[]'"
        )
    conn.commit()


def increment_operational_counter(interaction_type: str) -> None:
    conn = _get_db()
    if conn is None:
        return
    try:
        conn.execute(
            """
            INSERT INTO operational_counters(counter_date, interaction_type, count)
            VALUES (?, ?, 1)
            ON CONFLICT(counter_date, interaction_type)
            DO UPDATE SET count=count+1
            """,
            (date.today().isoformat(), interaction_type),
        )
        conn.commit()
    finally:
        conn.close()


def log_interaction(
    user_input: str,
    extracted_symptoms: List[str],
    extraction_source: str,
    pipeline_stages: Any,
    recommendation: Dict[str, Any],
    red_flags: Optional[List[Any]] = None,
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
    *,
    research_consent: bool = False,
    consent_version: Optional[str] = None,
    language: Optional[str] = None,
    input_mode: Optional[str] = None,
    trace: Optional[Dict[str, Any]] = None,
    headache: Optional[Dict[str, Any]] = None,
    severity_map: Optional[Dict[str, Any]] = None,
) -> str:
    """Persist raw consultation data only when research consent was granted."""
    if _disabled:
        return "disabled"
    if not research_consent:
        increment_operational_counter(interaction_type)
        return "not_persisted"

    interaction_id = uuid.uuid4().hex[:12]
    action = recommendation.get("action", "unknown")
    recommendations = []
    for row in recommendation.get("recommendations", []) or []:
        recommendations.append(
            {
                "brand": row.get("brand", ""),
                "generic": row.get(
                    "active_ingredients",
                    row.get("generic_name", row.get("generic", "")),
                ),
                "category": row.get("drug_category"),
                "reasons": row.get("reasons"),
                "min_age": row.get("min_age"),
                "dosage_form": row.get("dosage_form"),
            }
        )

    effective_trace = trace or {
        "trace_version": TRACE_SCHEMA_VERSION,
        "engine": {
            "engine_id": ENGINE_ID,
            "architecture": "knowledge_based_expert_system_with_pretrained_semantic_component",
            "automatically_trained_on_logs": False,
        },
        "stages": pipeline_stages or [],
        "decision": {
            "final_action": action,
            "severity": severity,
            "clarification": {
                "answer": clarification,
                "context_override": context_override,
            }
            if clarification or context_override
            else None,
            "duration": {
                "symptom": duration_symptom,
                "value": duration_value,
                "days": duration_days,
                "result": interaction_type,
            }
            if duration_symptom
            else None,
            "recommendation_filtering": {
                "patient_age": age,
                "returned_brands": [
                    row.get("brand")
                    for row in recommendation.get("recommendations", []) or []
                ],
            },
        },
    }
    stages = []
    for number, stage in enumerate(effective_trace.get("stages", []), start=1):
        row = dict(stage)
        row["step"] = number
        stages.append(row)

    headache_snapshot = headache
    if headache_snapshot is None and headache_location:
        # Compatibility only; new routes send the full server-derived snapshot.
        headache_snapshot = {
            "key": headache_location,
            "danger": headache_danger,
            "source": "legacy_location_key",
        }

    entry = {
        "interaction_id": interaction_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id or uuid.uuid4().hex[:8],
        "interaction_type": interaction_type,
        "user_input": user_input,
        "extracted_symptoms": extracted_symptoms,
        "extraction_source": extraction_source,
        "red_flags": red_flags or [],
        "pipeline_stages": stages,
        "action": action,
        "recommendations": recommendations,
        "clarification": clarification,
        "context_override": context_override,
        "severity": severity,
        "age": age,
        "pipeline_detail": {
            "trace": effective_trace,
            "headache": headache_snapshot,
            "severity_map": severity_map or {},
            "duration": {
                "symptom": duration_symptom,
                "value": duration_value,
                "days": duration_days,
            }
            if duration_symptom
            else None,
        },
        "recommendation_detail": {
            "action": action,
            "clarification_question": recommendation.get("question"),
            "clarification_options": [
                {"label": option.get("label"), "value": option.get("value")}
                for option in recommendation.get("options", []) or []
            ],
            "message": recommendation.get("message"),
        },
        "research_consent": 1,
        "consent_version": consent_version or CONSENT_VERSION,
        "language": language or "unspecified",
        "input_mode": input_mode or "text",
        "trace_version": int(effective_trace.get("trace_version", TRACE_SCHEMA_VERSION)),
        "engine_id": effective_trace.get("engine", {}).get("engine_id", ENGINE_ID),
    }
    conn = _get_db()
    if conn is None:
        return "write_failed"
    try:
        columns = list(entry)
        conn.execute(
            f"INSERT INTO interaction_logs ({','.join(columns)}) "
            f"VALUES ({','.join('?' for _ in columns)})",
            [
                json.dumps(entry[column], ensure_ascii=False, default=str)
                if column in _JSON_COLUMNS
                else entry[column]
                for column in columns
            ],
        )
        conn.commit()
    finally:
        conn.close()
    log.info(
        "Stored consented interaction %s (type=%s, symptoms=%d, action=%s)",
        interaction_id,
        interaction_type,
        len(extracted_symptoms),
        action,
    )
    return interaction_id


def _parse_log(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for column in _JSON_COLUMNS:
        value = result.get(column)
        if isinstance(value, str):
            try:
                result[column] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result[column] = {} if column.endswith("detail") else []
    result["legacy_unconsented"] = not bool(result.get("research_consent"))
    return result


def get_interaction_logs(
    limit: int = 500, offset: int = 0, search: str = ""
) -> List[Dict[str, Any]]:
    conn = _get_db()
    if conn is None:
        return []
    try:
        where, params = "", []
        if search:
            where = (
                "WHERE user_input LIKE ? OR extracted_symptoms LIKE ? "
                "OR interaction_id LIKE ? OR session_id LIKE ?"
            )
            like = f"%{search}%"
            params = [like, like, like, like]
        rows = conn.execute(
            f"SELECT * FROM interaction_logs {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [_parse_log(row) for row in rows]
    finally:
        conn.close()


def get_session_trace(session_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_db()
    if conn is None:
        return None
    try:
        rows = conn.execute(
            "SELECT * FROM interaction_logs WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        if not rows:
            return None
        events = [_parse_log(row) for row in rows]
        interaction_ids = [event["interaction_id"] for event in events]
        placeholders = ",".join("?" for _ in interaction_ids)
        reviews = [
            _parse_review(row)
            for row in conn.execute(
                f"""
                SELECT r.*, u.full_name AS reviewer_name
                FROM interaction_reviews r
                LEFT JOIN admin_users u ON u.id=r.reviewer_id
                WHERE r.interaction_id IN ({placeholders})
                ORDER BY r.created_at
                """,
                interaction_ids,
            ).fetchall()
        ]
        adjudications = [
            _parse_adjudication(row)
            for row in conn.execute(
                f"""
                SELECT a.*, u.full_name AS adjudicator_name
                FROM interaction_adjudications a
                LEFT JOIN admin_users u ON u.id=a.adjudicator_id
                WHERE a.interaction_id IN ({placeholders})
                """,
                interaction_ids,
            ).fetchall()
        ]
        return {
            "session_id": session_id,
            "research_consent": bool(events[0].get("research_consent")),
            "events": events,
            "reviews": reviews,
            "adjudications": adjudications,
        }
    finally:
        conn.close()


def get_sessions(limit: int = 100, offset: int = 0, search: str = "") -> List[Dict[str, Any]]:
    """Return session summaries; details are loaded through get_session_trace."""
    conn = _get_db()
    if conn is None:
        return []
    try:
        where, params = "", []
        if search:
            where = (
                "WHERE session_id LIKE ? OR user_input LIKE ? "
                "OR extracted_symptoms LIKE ?"
            )
            like = f"%{search}%"
            params = [like, like, like]
        rows = conn.execute(
            f"""
            SELECT session_id, MIN(id) first_id, MIN(timestamp) started_at,
                   MAX(timestamp) ended_at, COUNT(*) event_count,
                   MAX(research_consent) research_consent,
                   GROUP_CONCAT(interaction_id) interaction_ids
            FROM interaction_logs {where}
            GROUP BY session_id
            ORDER BY first_id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        ).fetchall()
        summaries = []
        for row in rows:
            summary = dict(row)
            first = conn.execute(
                "SELECT user_input, extracted_symptoms, action, pipeline_detail, research_consent "
                "FROM interaction_logs WHERE id=?",
                (summary.pop("first_id"),),
            ).fetchone()
            summary.update(_parse_log(first))
            summary["research_consent"] = bool(summary["research_consent"])
            summary["review_count"] = conn.execute(
                """
                SELECT COUNT(*) c FROM interaction_reviews
                WHERE interaction_id IN (
                    SELECT interaction_id FROM interaction_logs WHERE session_id=?
                )
                """,
                (summary["session_id"],),
            ).fetchone()["c"]
            summary["adjudicated"] = bool(
                conn.execute(
                    """
                    SELECT COUNT(*) c FROM interaction_adjudications
                    WHERE interaction_id IN (
                        SELECT interaction_id FROM interaction_logs WHERE session_id=?
                    )
                    """,
                    (summary["session_id"],),
                ).fetchone()["c"]
            )
            summaries.append(summary)
        return summaries
    finally:
        conn.close()


def count_interaction_logs(search: str = "") -> int:
    conn = _get_db()
    if conn is None:
        return 0
    try:
        if not search:
            return conn.execute("SELECT COUNT(*) c FROM interaction_logs").fetchone()["c"]
        like = f"%{search}%"
        return conn.execute(
            "SELECT COUNT(*) c FROM interaction_logs "
            "WHERE user_input LIKE ? OR extracted_symptoms LIKE ?",
            (like, like),
        ).fetchone()["c"]
    finally:
        conn.close()


def count_logs_today() -> int:
    conn = _get_db()
    if conn is None:
        return 0
    try:
        return conn.execute(
            "SELECT COUNT(*) c FROM interaction_logs "
            "WHERE date(timestamp)=date('now','localtime')"
        ).fetchone()["c"]
    finally:
        conn.close()


def get_most_common_symptom() -> str:
    counts: Dict[str, int] = {}
    for row in get_interaction_logs(limit=999999):
        for symptom in row.get("extracted_symptoms", []):
            counts[symptom] = counts.get(symptom, 0) + 1
    return max(counts, key=counts.get) if counts else ""


def submit_review(interaction_id: str, reviewer_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    _validate_review_payload(payload)
    conn = _get_db()
    if conn is None:
        raise RuntimeError("Database unavailable")
    try:
        interaction = conn.execute(
            "SELECT research_consent, interaction_type FROM interaction_logs WHERE interaction_id=?",
            (interaction_id,),
        ).fetchone()
        if not interaction:
            raise ValueError("Interaction not found")
        if not interaction["research_consent"]:
            raise ValueError("Legacy or unconsented interactions are not review-eligible")
        if interaction["interaction_type"] not in {
            "analysis",
            "triage",
            "initial_analysis",
        }:
            raise ValueError("Only the initial assessment is review-eligible")
        missed_symptoms = payload.get("missed_symptoms", [])
        correct_symptoms = payload.get("correct_symptoms")
        expected_symptoms = payload.get("expected_symptoms")
        if correct_symptoms is None:
            correct_symptoms = [
                label
                for label in (expected_symptoms or [])
                if label not in set(missed_symptoms)
            ]
        if expected_symptoms is None:
            expected_symptoms = list(
                dict.fromkeys([*correct_symptoms, *missed_symptoms])
            )
        values = {
            "expected_symptoms": expected_symptoms,
            "correct_symptoms": correct_symptoms,
            "missed_symptoms": missed_symptoms,
            "expected_red_flags": payload.get("expected_red_flags", []),
            "expected_action": payload["expected_action"],
            "recommendation_appropriateness": payload["recommendation_appropriateness"],
            "expected_medicines": payload.get("expected_medicines", []),
            "error_category": payload.get("error_category"),
            "reviewer_confidence": int(payload["reviewer_confidence"]),
            "notes": payload.get("notes"),
        }
        conn.execute(
            """
            INSERT INTO interaction_reviews
                (interaction_id, reviewer_id, expected_symptoms, correct_symptoms,
                 missed_symptoms,
                 expected_red_flags, expected_action,
                 recommendation_appropriateness, expected_medicines,
                 error_category, reviewer_confidence, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(interaction_id, reviewer_id) DO UPDATE SET
                expected_symptoms=excluded.expected_symptoms,
                correct_symptoms=excluded.correct_symptoms,
                missed_symptoms=excluded.missed_symptoms,
                expected_red_flags=excluded.expected_red_flags,
                expected_action=excluded.expected_action,
                recommendation_appropriateness=excluded.recommendation_appropriateness,
                expected_medicines=excluded.expected_medicines,
                error_category=excluded.error_category,
                reviewer_confidence=excluded.reviewer_confidence,
                notes=excluded.notes,
                updated_at=datetime('now','localtime')
            """,
            (
                interaction_id,
                reviewer_id,
                json.dumps(values["expected_symptoms"]),
                json.dumps(values["correct_symptoms"]),
                json.dumps(values["missed_symptoms"]),
                json.dumps(values["expected_red_flags"]),
                values["expected_action"],
                values["recommendation_appropriateness"],
                json.dumps(values["expected_medicines"]),
                values["error_category"],
                values["reviewer_confidence"],
                values["notes"],
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM interaction_reviews WHERE interaction_id=? AND reviewer_id=?",
            (interaction_id, reviewer_id),
        ).fetchone()
        return _parse_review(row)
    finally:
        conn.close()


def adjudicate(interaction_id: str, adjudicator_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    _validate_adjudication_payload(payload)
    conn = _get_db()
    if conn is None:
        raise RuntimeError("Database unavailable")
    try:
        eligible = conn.execute(
            "SELECT research_consent, interaction_type FROM interaction_logs WHERE interaction_id=?",
            (interaction_id,),
        ).fetchone()
        if not eligible:
            raise ValueError("Interaction not found")
        if not eligible["research_consent"]:
            raise ValueError("Legacy or unconsented interactions cannot be adjudicated")
        if eligible["interaction_type"] not in {
            "analysis",
            "triage",
            "initial_analysis",
        }:
            raise ValueError("Only the initial assessment can be adjudicated")
        conn.execute(
            """
            INSERT INTO interaction_adjudications
                (interaction_id, adjudicator_id, final_symptoms, final_red_flags,
                 final_action, recommendation_appropriateness,
                 expected_medicines, notes, adjudicated_at)
            VALUES (?,?,?,?,?,?,?,?,datetime('now','localtime'))
            ON CONFLICT(interaction_id) DO UPDATE SET
                adjudicator_id=excluded.adjudicator_id,
                final_symptoms=excluded.final_symptoms,
                final_red_flags=excluded.final_red_flags,
                final_action=excluded.final_action,
                recommendation_appropriateness=excluded.recommendation_appropriateness,
                expected_medicines=excluded.expected_medicines,
                notes=excluded.notes,
                adjudicated_at=datetime('now','localtime')
            """,
            (
                interaction_id,
                adjudicator_id,
                json.dumps(payload.get("final_symptoms", [])),
                json.dumps(payload.get("final_red_flags", [])),
                payload["final_action"],
                payload["recommendation_appropriateness"],
                json.dumps(payload.get("expected_medicines", [])),
                payload.get("notes"),
            ),
        )
        conn.commit()
        return _parse_adjudication(
            conn.execute(
                "SELECT * FROM interaction_adjudications WHERE interaction_id=?",
                (interaction_id,),
            ).fetchone()
        )
    finally:
        conn.close()


def get_aggregate_metrics() -> Dict[str, Any]:
    conn = _get_db()
    if conn is None:
        return {}
    try:
        rows = conn.execute(
            """
            SELECT l.interaction_id, l.extracted_symptoms, l.action,
                   a.final_symptoms, a.final_action,
                   a.recommendation_appropriateness
            FROM interaction_logs l
            JOIN interaction_adjudications a USING(interaction_id)
            WHERE l.research_consent=1
              AND l.interaction_type IN ('analysis','triage','initial_analysis')
            """
        ).fetchall()
        cases = []
        case_rows = []
        for row in rows:
            predicted = json.loads(row["extracted_symptoms"] or "[]")
            expected = json.loads(row["final_symptoms"] or "[]")
            metric = case_metrics(predicted, expected)
            metric.update(
                {
                    "interaction_id": row["interaction_id"],
                    "predicted_action": _normalize_action(row["action"]),
                    "expected_action": row["final_action"],
                    "action_match": _normalize_action(row["action"]) == row["final_action"],
                }
            )
            case_rows.append(metric)
            cases.append({"predicted": predicted, "expected": expected})
        reviews = [
            _parse_review(row)
            for row in conn.execute(
                """
                SELECT r.* FROM interaction_reviews r
                JOIN interaction_logs l USING(interaction_id)
                WHERE l.research_consent=1
                """
            ).fetchall()
        ]
        aggregate = aggregate_metrics(cases)
        aggregate["action_accuracy"] = (
            sum(1 for row in case_rows if row["action_match"]) / len(case_rows)
            if case_rows
            else None
        )
        return {
            "eligibility": "consented_and_adjudicated_only",
            "aggregate": aggregate,
            "clinical_appropriateness": clinical_appropriateness_rate(
                row["recommendation_appropriateness"] for row in rows
            ),
            "inter_reviewer_agreement": multilabel_reviewer_kappa(reviews),
            "cases": case_rows,
        }
    finally:
        conn.close()


def get_operational_summary() -> Dict[str, Any]:
    conn = _get_db()
    if conn is None:
        return {}
    try:
        counts = conn.execute(
            """
            SELECT
              COUNT(*) total,
              SUM(CASE WHEN research_consent=1 THEN 1 ELSE 0 END) consented,
              SUM(CASE WHEN research_consent=0 THEN 1 ELSE 0 END) legacy_unconsented
            FROM interaction_logs
            """
        ).fetchone()
        reviews = conn.execute("SELECT COUNT(*) c FROM interaction_reviews").fetchone()["c"]
        adjudicated = conn.execute(
            "SELECT COUNT(*) c FROM interaction_adjudications"
        ).fetchone()["c"]
        declined = conn.execute(
            "SELECT COALESCE(SUM(count),0) c FROM operational_counters"
        ).fetchone()["c"]
        return {
            **dict(counts),
            "independent_reviews": reviews,
            "adjudicated": adjudicated,
            "anonymous_nonpersistent_events": declined,
        }
    finally:
        conn.close()


def research_records() -> List[Dict[str, Any]]:
    conn = _get_db()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            SELECT l.*, a.final_symptoms, a.final_red_flags, a.final_action,
                   a.recommendation_appropriateness, a.expected_medicines,
                   a.adjudicated_at
            FROM interaction_logs l
            JOIN interaction_adjudications a USING(interaction_id)
            WHERE l.research_consent=1
              AND l.interaction_type IN ('analysis','triage','initial_analysis')
            ORDER BY l.id
            """
        ).fetchall()
        result = []
        for row in rows:
            parsed = _parse_log(row)
            result.append(
                {
                    "record_id": parsed["interaction_id"],
                    "text": deidentify_text(parsed.get("user_input", "")),
                    "language": parsed.get("language") or "unspecified",
                    "input_mode": parsed.get("input_mode") or "text",
                    "predicted_labels": parsed.get("extracted_symptoms", []),
                    "final_labels": json.loads(row["final_symptoms"] or "[]"),
                    "final_red_flags": json.loads(row["final_red_flags"] or "[]"),
                    "safety_action": row["final_action"],
                    "recommendation_judgment": row[
                        "recommendation_appropriateness"
                    ],
                    "expected_medicines": json.loads(
                        row["expected_medicines"] or "[]"
                    ),
                    "trace_version": parsed.get("trace_version"),
                    "engine_id": parsed.get("engine_id"),
                    "adjudicated_at": row["adjudicated_at"],
                }
            )
        return result
    finally:
        conn.close()


def export_research_jsonl() -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in research_records()
    )


def export_research_csv() -> str:
    rows = research_records()
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, dict))
                else value
                for key, value in row.items()
            }
        )
    return buf.getvalue()


def research_manifest() -> Dict[str, Any]:
    rows = research_records()
    return {
        "dataset_name": "mendo-domain-expert-field-validation",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(rows),
        "eligibility": "research_consent=true AND administrator_adjudicated",
        "deidentification": (
            "rule-based removal of email, telephone, explicit name/address, "
            "birth-date, and common numeric identifier patterns"
        ),
        "trace_versions": sorted(
            {row["trace_version"] for row in rows if row.get("trace_version") is not None}
        ),
        "engine_ids": sorted(
            {row["engine_id"] for row in rows if row.get("engine_id")}
        ),
        "automatic_production_training": False,
    }


def export_logs_as_csv() -> str:
    rows = get_interaction_logs(limit=999999)
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (list, dict))
                else value
                for key, value in row.items()
            }
        )
    return buf.getvalue()


def export_logs_as_json() -> str:
    return json.dumps(get_interaction_logs(limit=999999), ensure_ascii=False, indent=2)


def export_logs_as_pdf() -> bytes:
    """Operational export; intentionally imports the optional PDF dependency lazily."""
    rows = get_interaction_logs(limit=999999)
    if not rows:
        return b""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Mendo consultation audit", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=8)
    for row in rows:
        summary = (
            f"{row['interaction_id']} | {row['timestamp']} | "
            f"{', '.join(row.get('extracted_symptoms', [])) or 'No labels'} | "
            f"{row.get('action') or 'unknown'}"
        )
        pdf.multi_cell(0, 5, summary)
    return bytes(pdf.output())


def deidentify_text(text: str) -> str:
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[EMAIL]",
        text or "",
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"(?<!\d)(?:\+?63|0)?9\d{9}(?!\d)|(?<!\d)\d{3}[- ]\d{3}[- ]\d{4}(?!\d)",
        "[PHONE]",
        text,
    )
    text = re.sub(
        r"\b(?:my name is|ako si|pangalan ko(?: ay| si)?|"
        r"ngalan nako(?: kay)?)\s+[a-zñ]+(?:\s+[a-zñ]+){0,2}",
        "[NAME]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:I am|I'm)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}",
        "[NAME]",
        text,
    )
    text = re.sub(
        r"\b(?:address|tirahan|puy-anan)\s*(?:ko|nako)?\s*(?:is|ay|:)?"
        r"\s+[^,.;\n]{3,60}",
        "[ADDRESS]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:dob|birthdate|date of birth|birthday|kaarawan)\s*(?:is|ay|:)?"
        r"\s+\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b",
        "[BIRTH_DATE]",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?<!\d)\d{4}-\d{4}-\d{4}(?!\d)", "[IDENTIFIER]", text)
    return text


def _parse_review(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in (
        "expected_symptoms",
        "correct_symptoms",
        "missed_symptoms",
        "expected_red_flags",
        "expected_medicines",
    ):
        if isinstance(result.get(key), str):
            result[key] = json.loads(result[key] or "[]")
    return result


def _parse_adjudication(row: sqlite3.Row | Dict[str, Any]) -> Dict[str, Any]:
    result = dict(row)
    for key in ("final_symptoms", "final_red_flags", "expected_medicines"):
        if isinstance(result.get(key), str):
            result[key] = json.loads(result[key] or "[]")
    return result


def _validate_review_payload(payload: Dict[str, Any]) -> None:
    if payload.get("expected_action") not in {
        "recommend",
        "clarify",
        "refer",
        "no_match",
    }:
        raise ValueError("Invalid expected_action")
    if payload.get("recommendation_appropriateness") not in {
        "appropriate",
        "inappropriate",
        "not_applicable",
        "uncertain",
    }:
        raise ValueError("Invalid recommendation_appropriateness")
    confidence = int(payload.get("reviewer_confidence", 0))
    if not 1 <= confidence <= 5:
        raise ValueError("reviewer_confidence must be between 1 and 5")


def _validate_adjudication_payload(payload: Dict[str, Any]) -> None:
    if payload.get("final_action") not in {
        "recommend",
        "clarify",
        "refer",
        "no_match",
    }:
        raise ValueError("Invalid final_action")
    if payload.get("recommendation_appropriateness") not in {
        "appropriate",
        "inappropriate",
        "not_applicable",
    }:
        raise ValueError("Invalid recommendation_appropriateness")


def _normalize_action(action: Optional[str]) -> str:
    return {
        "triage": "refer",
        "refer": "refer",
        "ask_clarify": "clarify",
        "clarify": "clarify",
        "recommend": "recommend",
        "no_match": "no_match",
    }.get(action or "", action or "no_match")


def migrate_jsonl_to_sqlite() -> int:
    """Runtime JSONL import was retired so consent cannot be bypassed."""
    return 0
