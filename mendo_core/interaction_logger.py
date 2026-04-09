"""Mendo Interaction Logger — records every consultation for Iteration 2 validation.

Each consultation interaction is saved as a JSON entry in `logs/interactions.jsonl`
(JSON-Lines format: one JSON object per line). This data is designed to be reviewed
by domain-expert annotators in Iteration 2 for validation of:
  - Symptom extraction correctness (precision / recall)
  - Recommendation appropriateness
  - Missed symptoms (false negatives)

Logged fields per interaction:
  - interaction_id     : unique identifier for this log entry
  - timestamp          : ISO-8601 datetime
  - session_id         : unique session identifier (persists across a consultation flow)
  - interaction_type   : "initial_analysis" | "cough_clarification" | "context_clarification"
  - user_input         : raw text the user typed / spoke
  - extracted_symptoms : final symptom labels
  - extraction_source  : which pipeline stage produced final symptoms
  - red_flags          : list of red-flag categories triggered
  - pipeline_stages    : per-stage extraction details (step1 dictionary, step2 semantic)
  - action             : "recommend" | "ask_clarify" | "triage" | "no_match"
  - recommendations    : list of recommended medicines (brand + generic)
  - clarification      : follow-up clarification value (e.g. COUGH_DRY, DIARRHEA_NON_INFECTIOUS)
  - context_override   : explicit OLDCARTS context override when provided (e.g. DIARRHEA_FOOD_POISONING)
  - severity           : user-reported severity (1-10)
  - age                : user-reported age
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

# When True, log_interaction() silently skips writing.  Set by test fixtures.
_disabled = False


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
    context_override: Optional[str] = None,
    interaction_type: str = "initial_analysis",
    severity: Optional[int] = None,
    age: Optional[int] = None,
    session_id: Optional[str] = None,
) -> str:
    """Append one interaction record to the JSONL log file.

    Parameters
    ----------
    interaction_type : str
        One of "initial_analysis", "cough_clarification", "context_clarification".
    context_override : str | None
        Explicit OLDCARTS context override (e.g. DIARRHEA_FOOD_POISONING).

    Returns the generated interaction_id.
    """
    if _disabled:
        return "disabled"

    _ensure_log_dir()

    interaction_id = uuid.uuid4().hex[:12]

    # Build a clean list of recommended medicines (brand + generic only)
    rec_list = []
    action = recommendation.get("action", "unknown")
    if action == "recommend":
        for r in recommendation.get("recommendations", []):
            rec_list.append({
                "brand": r.get("brand", ""),
                "generic": r.get("active_ingredients", r.get("generic_name", r.get("generic", ""))),  # step4 uses 'active_ingredients'
            })

    # Number the pipeline stages for clarity (step1, step2, etc.)
    numbered_stages = []
    step_num = 1
    for stage in (pipeline_stages or []):
        stage_copy = dict(stage)
        stage_copy["step"] = step_num
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
    }

    try:
        with open(_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        log.info("Logged interaction %s (type=%s, %d symptoms, action=%s)",
                 interaction_id, interaction_type, len(extracted_symptoms), action)
    except Exception as e:
        log.error("Failed to log interaction: %s", e)

    return interaction_id
