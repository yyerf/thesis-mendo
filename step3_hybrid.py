"""step3_hybrid.py

HYBRID NLP PIPELINE (Defense-friendly)

Idea:
- Step 1 (dictionary) for speed + predictable behavior on common phrases.
- Step 2 (embeddings) as a fallback when exact match fails (slang/paraphrase).

This gives you a strong panel line:
"We cascade from deterministic keyword matching to a transformer-based embedding
model only when needed, making the system both fast and robust."

Install for Step 2 fallback:
  python -m pip install sentence-transformers
"""

from __future__ import annotations

import argparse
import json
import re
from typing import List

from step1 import extract_symptoms as extract_symptoms_dictionary


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _dictionary_matches(user_input: str) -> List[dict]:
    """Return which symptom + phrase(s) matched in the dictionary stage."""
    try:
        from step1 import SYMPTOM_DICTIONARY  # type: ignore
    except Exception:
        return []

    normalized_text = _normalize(user_input)
    out: List[dict] = []
    for symptom, phrases in SYMPTOM_DICTIONARY.items():
        matched: List[str] = []
        for p in phrases:
            np = _normalize(p)
            if not np:
                continue
            if " " in np:
                if np in normalized_text:
                    matched.append(p)
            else:
                if re.search(rf"\b{re.escape(np)}\b", normalized_text):
                    matched.append(p)
        if matched:
            out.append({"symptom": symptom, "matched_phrases": matched[:3]})
    return out


_SEMANTIC_EXTRACTOR = None


def _get_semantic_extractor():
    """Lazy singleton to avoid re-loading the transformer every request."""
    global _SEMANTIC_EXTRACTOR
    if _SEMANTIC_EXTRACTOR is not None:
        return _SEMANTIC_EXTRACTOR

    from step2 import EmbeddingSymptomExtractor, SYMPTOM_ANCHORS

    _SEMANTIC_EXTRACTOR = EmbeddingSymptomExtractor(SYMPTOM_ANCHORS)
    return _SEMANTIC_EXTRACTOR


def extract_symptoms_hybrid(
    user_input: str,
    *,
    semantic_threshold: float = 0.65,
    semantic_top_margin: float = 0.08,
    semantic_max_symptoms: int = 2,
    enable_semantic_fallback: bool = True,
) -> List[str]:
    """Hybrid symptom extraction.

    1) Try dictionary-based extraction.
    2) If nothing found AND fallback enabled, try semantic extraction.

    Returns a distinct list of symptom labels.
    """

    detected = extract_symptoms_dictionary(user_input)
    if detected or not enable_semantic_fallback:
        return detected

    # Lazy import so step3 can still run without sentence-transformers installed
    try:
        from step2 import EmbeddingSymptomExtractor, SYMPTOM_ANCHORS
    except Exception:
        # If semantic components are not available, gracefully return dictionary result.
        return detected

    try:
        extractor = _get_semantic_extractor()
        semantic_detected, diag = extractor.analyze(user_input, threshold=semantic_threshold)
    except Exception:
        # If the semantic backend isn't available (e.g., dependency not installed),
        # fail safely by returning the deterministic result.
        return detected

    # Reduce false positives while still allowing multi-symptom output:
    # take the TOP-N symptoms that pass the threshold.
    # (semantic_top_margin is kept as a tunable argument, but selection is
    # primarily controlled by the threshold + top-N cap.)
    scored = sorted(
        ((m.symptom, float(m.score)) for m in diag if m.symptom in semantic_detected),
        key=lambda x: x[1],
        reverse=True,
    )
    selected = [symptom for symptom, _score in scored[:semantic_max_symptoms]]

    # Distinct merge (dictionary first)
    merged = list(dict.fromkeys(detected + selected))
    return merged


def extract_symptoms_hybrid_report(
    user_input: str,
    *,
    semantic_threshold: float,
    semantic_top_margin: float,
    semantic_max_symptoms: int,
    enable_semantic_fallback: bool,
) -> dict:
    """Like extract_symptoms_hybrid, but returns a structured report for benchmarking."""

    report: dict = {
        "input": user_input,
        "stages": [],
        "final": {"symptoms": []},
    }

    dict_symptoms = extract_symptoms_dictionary(user_input)
    dict_details = _dictionary_matches(user_input)
    report["stages"].append(
        {
            "stage": "dictionary",
            "used": True,
            "detected": dict_symptoms,
            "details": dict_details,
        }
    )

    if dict_symptoms or not enable_semantic_fallback:
        report["final"]["symptoms"] = dict_symptoms
        report["final"]["source"] = "dictionary" if dict_symptoms else "dictionary_only"
        return report

    try:
        extractor = _get_semantic_extractor()
        semantic_detected, diag = extractor.analyze(user_input, threshold=semantic_threshold)
        diag_sorted = sorted(
            [
                {
                    "symptom": m.symptom,
                    "score": float(m.score),
                    "best_anchor": m.best_anchor,
                }
                for m in diag
            ],
            key=lambda x: x["score"],
            reverse=True,
        )
    except Exception as e:
        report["stages"].append(
            {
                "stage": "semantic",
                "used": True,
                "available": False,
                "error": str(e),
            }
        )
        report["final"]["symptoms"] = []
        report["final"]["source"] = "none"
        return report

    # Select TOP-N symptoms that passed the threshold.
    candidates = [row for row in diag_sorted if row["symptom"] in semantic_detected]
    selected = [row["symptom"] for row in candidates[:semantic_max_symptoms]]

    report["stages"].append(
        {
            "stage": "semantic",
            "used": True,
            "available": True,
            "threshold": semantic_threshold,
            "top_margin": semantic_top_margin,
            "max_symptoms": semantic_max_symptoms,
            "detected_raw": semantic_detected,
            "detected_selected": selected,
            "scores": diag_sorted,
        }
    )

    report["final"]["symptoms"] = selected
    report["final"]["source"] = "semantic_fallback" if selected else "none"
    return report


def _interactive_loop(args: argparse.Namespace) -> int:
    print("Hybrid Symptom Extractor (type 'exit' to quit)")
    if args.flow:
        print("Tip: use --debug to show matches/scores.")
    print("")
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            return 0

        report = extract_symptoms_hybrid_report(
            user_input,
            semantic_threshold=args.semantic_threshold,
            semantic_top_margin=args.semantic_top_margin,
            semantic_max_symptoms=args.semantic_max_symptoms,
            enable_semantic_fallback=not args.no_semantic,
        )

        if args.json:
            print(json.dumps(report, ensure_ascii=False))
            continue

        if args.flow or args.debug:
            _print_flow(report, debug=args.debug)
        else:
            print("DETECTED:", report["final"]["symptoms"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Hybrid symptom extractor (dictionary + semantic fallback)")
    parser.add_argument("--text", type=str, default=None, help="Analyze a single input text")
    parser.add_argument("--interactive", action="store_true", help="Start an interactive prompt")
    parser.add_argument("--semantic-threshold", type=float, default=0.65, help="Semantic similarity threshold")
    parser.add_argument("--semantic-top-margin", type=float, default=0.08, help="Keep matches within this margin of top score")
    parser.add_argument("--semantic-max-symptoms", type=int, default=2, help="Max symptoms from semantic fallback")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic fallback (dictionary only)")
    parser.add_argument("--flow", action="store_true", help="Print step-by-step tagged flow output")
    parser.add_argument("--debug", action="store_true", help="Print deeper debug (matched phrases + top semantic scores)")
    parser.add_argument("--json", action="store_true", help="Print JSON per input (good for benchmarking logs)")
    args = parser.parse_args()

    if args.text is not None:
        report = extract_symptoms_hybrid_report(
            args.text,
            semantic_threshold=args.semantic_threshold,
            semantic_top_margin=args.semantic_top_margin,
            semantic_max_symptoms=args.semantic_max_symptoms,
            enable_semantic_fallback=not args.no_semantic,
        )
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.flow or args.debug:
            _print_flow(report, debug=args.debug)
        else:
            print("INPUT:", args.text)
            print("DETECTED:", report["final"]["symptoms"])
        return 0

    # Default behavior: interactive if no --text provided.
    if args.interactive or args.text is None:
        return _interactive_loop(args)

    return 0


def _print_flow(report: dict, *, debug: bool) -> None:
    """Pretty, thesis-panel-friendly flow output."""

    user_input = report.get("input", "")
    final = report.get("final", {})
    final_symptoms = final.get("symptoms", [])
    final_source = final.get("source", "unknown")

    print(f"INPUT:   {user_input}")

    # Stage 1: dictionary
    dict_stage = next((s for s in report.get("stages", []) if s.get("stage") == "dictionary"), None)
    if dict_stage is not None:
        dict_detected = dict_stage.get("detected", [])
        print(f"STAGE1:  DICTIONARY -> {dict_detected}")
        if debug and dict_stage.get("details"):
            for d in dict_stage["details"]:
                phrases = d.get("matched_phrases", [])
                print(f"         hit {d.get('symptom')}: {phrases}")

    # Stage 2: semantic
    sem_stage = next((s for s in report.get("stages", []) if s.get("stage") == "semantic"), None)
    if sem_stage is not None:
        if not sem_stage.get("available", True):
            print(f"STAGE2:  SEMANTIC (unavailable) -> error={sem_stage.get('error')}")
        else:
            thr = sem_stage.get("threshold")
            top_margin = sem_stage.get("top_margin")
            max_sym = sem_stage.get("max_symptoms")
            raw = sem_stage.get("detected_raw", [])
            selected = sem_stage.get("detected_selected", [])
            print(f"STAGE2:  SEMANTIC fallback -> selected={selected}")
            if debug:
                print(f"         params: threshold={thr} top_margin={top_margin} max={max_sym} raw={raw}")
                for row in sem_stage.get("scores", [])[:6]:
                    print(
                        f"         score {row['symptom']}: {row['score']:.4f} (anchor: {row['best_anchor']!r})"
                    )

    print(f"FINAL:   {final_symptoms}  (source={final_source})")


if __name__ == "__main__":
    raise SystemExit(main())
