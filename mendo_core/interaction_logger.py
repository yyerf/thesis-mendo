"""Mendo Interaction Logger — records every consultation for Iteration 2 validation.

Each consultation interaction is saved as a JSON entry in `logs/interactions.jsonl`
(JSON-Lines format: one JSON object per line). This data is designed to be reviewed
by domain-expert annotators in Iteration 2 for validation of:
  - Symptom extraction correctness (precision / recall)
  - Recommendation appropriateness
  - Missed symptoms (false negatives)

Logged fields per interaction:
  - timestamp          : ISO-8601 datetime
  - session_id         : unique session identifier
  - user_input         : raw text the user typed / spoke
  - detected_language  : language detected (if available)
  - extraction_source  : which pipeline stage produced final symptoms
  - red_flags          : list of red-flag categories triggered
  - extracted_symptoms : final symptom labels
  - pipeline_stages    : per-stage extraction details
  - recommendations    : list of recommended medicines (brand + generic)
  - action             : recommend | ask_clarify | red_flag
  - clarification      : follow-up cough clarification (if any)
  - severity           : user-reported severity (if any)
  - age                : user-reported age (if any)
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger("mendo.logger")

_LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
_LOG_FILE = _LOG_DIR / "interactions.jsonl"


def _ensure_log_dir():
    """Create the logs directory if it doesn't exist."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_interaction(
    user_input: str,
    extracted_symptoms: List[str],
    extraction_source: str,
    pipeline_stages: Any,
    recommendation: Dict[str, Any],
    red_flags: Optional[List[str]] = None,
    clarification: Optional[str] = None,
    severity: Optional[int] = None,
    age: Optional[int] = None,
    session_id: Optional[str] = None,
) -> str:
    """Append one interaction record to the JSONL log file.

    Returns the generated interaction_id.
    """
    _ensure_log_dir()

    interaction_id = uuid.uuid4().hex[:12]

    # Build a clean list of recommended medicines (brand + generic only)
    rec_list = []
    if recommendation.get("action") == "recommend":
        for r in recommendation.get("recommendations", []):
            rec_list.append({
                "brand": r.get("brand", ""),
                "generic": r.get("generic_name", r.get("generic", "")),
            })

    entry = {
        "interaction_id": interaction_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session_id": session_id or uuid.uuid4().hex[:8],
        "user_input": user_input,
        "extracted_symptoms": extracted_symptoms,
        "extraction_source": extraction_source,
        "red_flags": red_flags or [],
        "pipeline_stages": pipeline_stages,
        "action": recommendation.get("action", "unknown"),
        "recommendations": rec_list,
        "clarification": clarification,
        "severity": severity,
        "age": age,
    }

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info("Logged interaction %s (%d symptoms, action=%s)",
                 interaction_id, len(extracted_symptoms), entry["action"])
    except Exception as e:
        log.error("Failed to log interaction: %s", e)

    return interaction_id
