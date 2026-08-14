"""sailor_semantic.py

Semantic fallback backend powered by a local LLM (Sailor2) served by Ollama.

Why this exists:
- The MiniLM embedding backend (step2) is weak on code-switched Filipino:
  e.g. it ranked DIARRHEA above FEVER on a fever sentence and flagged
  RUNNY_NOSE for a blocked nose.
- Sailor2 is a Southeast-Asian-native LLM (Apache-2.0, base Qwen2.5,
  ~500B regional tokens incl. Cebuano). Running it locally via Ollama
  keeps patient data on-device (RA 10173) and adds zero Python deps —
  we only speak HTTP to http://127.0.0.1:11434.

Safety design (defense-critical, keep it this way):
- Closed-vocabulary constrained decode: a GBNF JSON-schema (SCHEMA_FORMAT)
  with a 13-label enum physically forbids any other output — the model
  cannot emit a label outside the list even if prompted maliciously.
- Few-shot examples are real conversation turns (anchoring), not inline text.
- temperature=0, max 120 output tokens.
- Fail-closed: unparseable output or HTTP failure RAISES so the caller
  records the semantic stage as unavailable and falls back to the
  deterministic dictionary result. The model can never override rules;
  downstream lexical guards / safety filters still veto its output.
- fallback_only=True: this backend runs ONLY when the dictionary found
  nothing (precision-first; also avoids LLM latency on every kiosk query).

Protocol: mirrors mendo_core.step2.EmbeddingSymptomExtractor.analyze()
so step3_hybrid can swap backends behind the _get_semantic_extractor()
factory without any other changes.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Dict, List, Tuple

from .step2 import SemanticMatch

SYMPTOM_LABELS: List[str] = [
    "HEADACHE",
    "FEVER",
    "COUGH_GENERAL",
    "COUGH_DRY",
    "COUGH_PRODUCTIVE",
    "SORE_THROAT",
    "STOMACH_ACHE",
    "BODY_ACHES",
    "DIARRHEA",
    "NASAL_CONGESTION",
    "RUNNY_NOSE",
    "RASHES",
    "ALLERGIC_RHINITIS",
]

_SYSTEM_PROMPT = """You are SYMPTOM-CODE, a strict symptom classifier for an offline OTC-medicine kiosk in the Philippines. Users may write in English, Tagalog, Cebuano/Bisaya, Taglish, or Jejemon.

Map the user's message to a JSON object {"symptoms": [...]} where the array entries are drawn ONLY from this closed vocabulary:
["HEADACHE", "FEVER", "COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE", "SORE_THROAT", "STOMACH_ACHE", "BODY_ACHES", "DIARRHEA", "NASAL_CONGESTION", "RUNNY_NOSE", "RASHES", "ALLERGIC_RHINITIS"]

Rules:
- Reply with ONLY the JSON object. No prose, no markdown, no explanations.
- {"symptoms": []} means the message does not clearly describe any symptom.
- A blocked/stuffed nose is NASAL_CONGESTION. A dripping/running nose is RUNNY_NOSE.
- Negated symptoms ("no fever", "wala nay ubo", "dili ubo") must NOT be listed.
- Blood, trauma, emergencies, or non-medical chit-chat -> {"symptoms": []} (the kiosk has a separate triage layer)."""

# Few-shot examples as real conversation turns — small models anchor on the
# LAST assistant message when examples sit inside the system prompt, which
# produced a spurious COUGH_DRY default. Real turns avoid that bias.
FEW_SHOT_EXAMPLES: List[Tuple[str, str]] = [
    ("masakit ang ulo ko", '["HEADACHE"]'),
    ("naay dugo sa akong tae", "[]"),
    ("my nose has been blocked since morning", '["NASAL_CONGESTION"]'),
    ("nagkalibang ko ug sakit tiyan", '["DIARRHEA", "STOMACH_ACHE"]'),
    ("pahabol lang to, wala na ko sakit", "[]"),
]

# GBNF-constrained schema: the model physically cannot emit a label outside
# the enum — this is the closed-vocabulary guarantee, not prompt trust.
SCHEMA_FORMAT = {
    "type": "object",
    "properties": {
        "symptoms": {
            "type": "array",
            "items": {"type": "string", "enum": SYMPTOM_LABELS},
        }
    },
    "required": ["symptoms"],
}


class LLMSymptomExtractor:
    """Local-LLM symptom extractor (Ollama HTTP API).

    Same public protocol as EmbeddingSymptomExtractor:
        analyze(user_input, threshold=...) -> (labels, List[SemanticMatch])

    threshold is accepted for interface compatibility; the LLM decides
    presence via constrained decode, so emitted labels carry score 1.0
    and non-emitted labels score 0.0 (an honest binary emission score).
    """

    fallback_only = True

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
        max_cache: int = 256,
    ) -> None:
        self.base_url = (base_url or os.getenv("MENDO_LLM_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.model = model or os.getenv("MENDO_LLM_MODEL", "sailor2:1b")
        self.timeout = float(timeout if timeout is not None else os.getenv("MENDO_LLM_TIMEOUT", "60"))
        self._cache: "OrderedDict[str, Tuple[List[str], List[SemanticMatch]]]" = OrderedDict()
        self._max_cache = max_cache

    # ── public protocol ────────────────────────────────────────────────────

    def analyze(
        self,
        user_input: str,
        threshold: float = 0.65,
    ) -> Tuple[List[str], List[SemanticMatch]]:
        """Return detected labels + per-label diagnostics (fail-closed)."""
        cached = self._cache_get(user_input)
        if cached is not None:
            return cached

        reply = self._generate(user_input)
        labels = self._parse_reply(reply)

        matches: List[SemanticMatch] = []
        for symptom in SYMPTOM_LABELS:
            emitted = symptom in labels
            matches.append(
                SemanticMatch(
                    symptom=symptom,
                    score=1.0 if emitted else 0.0,
                    best_anchor=f"llm_constrained_decode: {reply[:120]!r}",
                )
            )

        result = (labels, matches)
        self._cache_set(user_input, result)
        return result

    def warmup(self) -> None:
        """Force the Ollama endpoint (and model) to load before first query.

        Raises if the endpoint is unreachable — callers log and move on.
        """
        tags_url = f"{self.base_url}/api/tags"
        with urllib.request.urlopen(tags_url, timeout=3) as resp:  # noqa: S310 (localhost only)
            if resp.status != 200:
                raise RuntimeError(f"ollama tags probe failed with HTTP {resp.status}")

        # A tiny generation forces the model weights into memory so the
        # first real query doesn't pay the cold-start penalty.
        self._generate("[]")

    # ── ollama client ──────────────────────────────────────────────────────

    def _generate(self, user_input: str) -> str:
        messages: List[Dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        for user_turn, assistant_turn in FEW_SHOT_EXAMPLES:
            messages.append({"role": "user", "content": user_turn})
            messages.append({"role": "assistant", "content": assistant_turn})
        messages.append({"role": "user", "content": user_input})

        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "format": SCHEMA_FORMAT,
                "stream": False,
                "options": {"temperature": 0, "num_predict": 120},
            }
        ).encode("utf-8")

        req = urllib.request.Request(  # noqa: S310 (localhost only)
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as e:
            raise RuntimeError(
                f"semantic backend unreachable (url={self.base_url}, model={self.model}): {e}"
            ) from e

        content = (payload.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(f"semantic backend returned an empty reply for {self.model!r}")
        return content.strip()

    # ── fail-closed parsing ────────────────────────────────────────────────

    @staticmethod
    def _parse_reply(reply: str) -> List[str]:
        """Extract a closed-vocabulary label list, or raise.

        Accepts a bare JSON array, an object like {"symptoms": [...]}, and
        array text wrapped in markdown fences. Anything else is a backend
        failure, not an empty detection.
        """
        text = reply.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Last resort: pull the first [...] block out of stray prose.
            block = re.search(r"\[.*?\]", text, flags=re.DOTALL)
            if block is None:
                raise ValueError(f"semantic backend produced unparseable output: {reply[:160]!r}")
            try:
                data = json.loads(block.group(0))
            except json.JSONDecodeError as e:
                raise ValueError(f"semantic backend produced unparseable output: {reply[:160]!r}") from e

        if isinstance(data, dict):
            if "symptoms" in data or "labels" in data:
                data = data.get("symptoms", data.get("labels", []))
            else:
                # The model sometimes emits {"HEADACHE": true, "FEVER": true}
                # instead of a JSON array. Accept closed-vocabulary keys with
                # truthy values; anything else is still a failure.
                label_keys = [k for k in data if isinstance(k, str) and k.upper() in SYMPTOM_LABELS]
                if not label_keys:
                    raise ValueError(f"semantic backend produced non-list output: {reply[:160]!r}")
                return [k.upper() for k in label_keys if data[k]]
        if not isinstance(data, list):
            raise ValueError(f"semantic backend produced non-list output: {reply[:160]!r}")

        labels: List[str] = []
        for item in data:
            if not isinstance(item, str):
                continue
            label = item.strip().upper()
            if label in SYMPTOM_LABELS and label not in labels:
                labels.append(label)
        return labels

    # ── tiny LRU cache (kiosk phrases repeat a lot) ────────────────────────

    def _cache_get(self, key: str):
        hit = self._cache.get(key)
        if hit is not None:
            self._cache.move_to_end(key)
        return hit

    def _cache_set(self, key: str, value) -> None:
        self._cache[key] = value
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)


def _probe_available(base_url: str | None = None, timeout: float = 3.0) -> bool:
    """Cheap availability probe (used by docs/scripts, never by the safety path)."""
    url = (base_url or os.getenv("MENDO_LLM_URL", "http://127.0.0.1:11434")).rstrip("/")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    import sys

    ex = LLMSymptomExtractor()
    print(f"endpoint={ex.base_url} model={ex.model}")
    if not _probe_available():
        print("Ollama is not running. Start it with `ollama serve` and `ollama pull sailor2:1b`.")
        sys.exit(1)
    for text in sys.argv[1:] or ["masakit ulo ko", "nagkalibang ko", "blocked nose since morning"]:
        t0 = time.time()
        labels, diag = ex.analyze(text)
        print(f"{text!r} -> {labels} ({time.time() - t0:.2f}s)")
        for m in diag:
            if m.score > 0:
                print(f"    {m.symptom} 1.0")
