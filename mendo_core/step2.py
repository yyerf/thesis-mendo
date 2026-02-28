"""step2.py

LEVEL UP: Semantic Symptom Extraction using Vector Embeddings (Sentence Transformers)

Why this exists:
- Step 1 (dictionary) is fast + deterministic, but it fails on paraphrases/slang
  like: "My head feels like it's exploding" (no exact keyword "headache").

What Step 2 does:
- Represent sentences as vectors (embeddings) in a shared multilingual space.
- Compare the user's input vs. a small set of "anchor sentences" per symptom.
- If similarity is high enough, we mark that symptom as detected.

This is still thesis-friendly because you can explain it clearly:
- "We convert sentences to coordinates, then measure cosine similarity."

Install:
  python -m pip install sentence-transformers

Note:
- This is NOT training a model. We are using a pre-trained multilingual encoder.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Dict, Iterable, List, Tuple


# ---------------------------------------------------------------------------
# 1) ANCHORS: symptom label -> a few "gold standard" example sentences
# ---------------------------------------------------------------------------
# Keep these short and clear. Add more anchors to improve recall.
# Tip: include variations across languages + common student slang.

SYMPTOM_ANCHORS: Dict[str, List[str]] = {
    "HEADACHE": [
        "My head hurts badly",
        "I have a pounding headache",
        "My head feels like it's exploding",
        "masakit ang ulo ko",
        "parang sasabog ulo ko",
        "labad ang ulo",
        "sakit ulo",
        "labad akong ulo",
        "sumakit ulo ko",
        "sumasakit ang ulo ko",
        "may headache",
        "my head hurts",
    ],
    "COUGH_DRY": [
        "I have a dry cough",
        "I keep coughing but there is no phlegm",
        "tickly cough",
        "walang plema",
        "walay plema",
        "tuyong ubo",
        "uga nga ubo",
    ],
    "COUGH_PRODUCTIVE": [
        "I have a cough with phlegm",
        "wet cough with mucus",
        "productive cough",
        "chest congestion with phlegm",
        "may plema",
        "naay plema",
        "basang ubo",
        "ubo na naay plema",
    ],
    "COUGH_GENERAL": [
        "I have a cough",
        "I keep coughing",
        "inuubo ako",
        "may ubo ako",
        "gi ubo ko",
    ],
    "FEVER": [
        "I have a high temperature",
        "I feel feverish and hot",
        "my body feels hot",
        "mataas ang lagnat",
        "nilalagnat ako",
        "mainit ang katawan ko",
        "mainit lang ang katawan ko",
        "hilanat ko",
        "gihilanat ko",
        "init akong lawas",
        "init kaayo akong lawas",
        "sinat lang",
        "may sinat",
        "trangkaso",
        "kalintura",
    ],
    "BODY_ACHES": [
        "my body aches",
        "muscle pain and body aches",
        "masakit katawan ko",
        "sakit lawas",
        "ngalay ang katawan",
        "sakit tibuok lawas",
        "panuhot sa likod",
        "sakit sa likod",
        "mabigat ang katawan",
        "mabigat ang pakiramdam",
        "katawan lang ang masakit",
        "feeling heavy body",
    ],
    "NASAL_CONGESTION": [
        "my nose is blocked",
        "stuffy nose",
        "nasal congestion",
        "barado ilong",
        "bara ang ilong",
        "weird ang ilong ko",
        "weird akong ilong",
    ],
    "RUNNY_NOSE": [
        "runny nose",
        "my nose is running",
        "sipon",
        "tumutulo ilong",
        "nagatulo akong ilong",
    ],
    "ALLERGIC_RHINITIS": [
        "I have allergies and keep sneezing",
        "itchy nose and watery eyes",
        "bahing nang bahing",
        "makati ilong",
        "katol ilong",
        "makati ang ilong at mata",
    ],
    "RASHES": [
        "I have skin rashes",
        "I have a rash on my skin",
        "I have hives and my skin is itchy",
        "may pantal ako",
        "may butlig ako",
        "makati ang balat ko at may pantal",
        "katol akong panit",
        "katol akong lawas",
        "makati akong lawas",
        "my body is itchy",
        "my skin is red and itchy",
        "nagpula akong panit unya katol siya",
    ],
    "DIARRHEA": [
        "I have diarrhea",
        "loose stool",
        "watery stool",
        "nagtatae ako",
        "nagkalibang ko",
        "basa akong tae",
        "gikalibanga",
        "sige kog kalibang",
        "lbm since morning",
    ],
    "STOMACH_ACHE": [
        "I have a stomach ache",
        "I have stomach pain",
        "my stomach hurts badly",
        "my stomach is painful",
        "masakit ang tiyan ko",
        "masakit tiyan ko",
        "sakit tiyan",
        "sakit ang tiyan",
        "sakit akong tiyan",
        "mahapdi ang sikmura ko",
        "mahapdi sikmura",
        "kabag",
        "grabe ang kabag ko",
        "aslom akong tiyan",
        "gihiluan",
        "masusuka ako at sakit tiyan",
        "sakit tiyan ko",
        "acidic stomach",
        "hyperacidity",
    ],
}


# ---------------------------------------------------------------------------
# 2) EMBEDDING EXTRACTOR
# ---------------------------------------------------------------------------

@dataclass
class SemanticMatch:
    symptom: str
    score: float
    best_anchor: str


class EmbeddingSymptomExtractor:
    """Semantic symptom extractor using cosine similarity against anchors."""

    def __init__(
        self,
        anchors: Dict[str, List[str]],
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ) -> None:
        # Allow swapping in a fine-tuned/local model without code changes.
        # Example (to test LaBSE or fine-tuned model):
        #   export MENDO_SENTENCE_TRANSFORMER_MODEL=sentence-transformers/LaBSE
        #   export MENDO_SENTENCE_TRANSFORMER_MODEL=models/mendo-miniLM-finetuned
        model_name = os.environ.get("MENDO_SENTENCE_TRANSFORMER_MODEL", model_name)

        # Best-effort: reduce third-party noise (progress bars / warnings).
        # These affect only the current process.
        os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
        os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

        # Reduce noisy logs from Transformers / HF Hub when running demos.
        try:
            from transformers.utils import logging as _tlog  # type: ignore

            _tlog.set_verbosity_error()
        except Exception:
            pass
        try:
            from huggingface_hub.utils import logging as _hlog  # type: ignore

            _hlog.set_verbosity_error()
        except Exception:
            pass

        # Import here so step2.py can still be opened/run without the dependency.
        try:
            from sentence_transformers import SentenceTransformer, util  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "Missing dependency: sentence-transformers. "
                "Install with: python -m pip install sentence-transformers"
            ) from e

        self._util = util
        self._model = SentenceTransformer(model_name)
        self._anchors = anchors

        # Pre-encode all anchors once (speed). We keep them per symptom.
        self._anchor_embeddings = {
            symptom: self._model.encode(phrases, convert_to_tensor=True)
            for symptom, phrases in self._anchors.items()
        }

    def analyze(
        self,
        user_input: str,
        threshold: float = 0.50,
    ) -> Tuple[List[str], List[SemanticMatch]]:
        """Return detected symptoms + scored debug info.

        Args:
            user_input: raw user sentence (mixed language)
            threshold: similarity cutoff; 0.4 = loose, 0.7 = strict

        Returns:
            detected_labels: list of symptom labels (distinct)
            matches: per-symptom best-match diagnostics
        """

        # Encode user input into a vector.
        user_emb = self._model.encode(user_input, convert_to_tensor=True)

        detected: List[str] = []
        diagnostics: List[SemanticMatch] = []

        for symptom, phrases in self._anchors.items():
            anchor_embs = self._anchor_embeddings[symptom]

            # cosine similarity: shape (1, num_anchors)
            scores = self._util.cos_sim(user_emb, anchor_embs)[0]

            # Find best anchor index and score
            best_idx = int(scores.argmax())
            best_score = float(scores[best_idx])
            best_anchor = phrases[best_idx]

            diagnostics.append(SemanticMatch(symptom=symptom, score=best_score, best_anchor=best_anchor))

            if best_score >= threshold:
                detected.append(symptom)

        # distinct, stable order
        detected = list(dict.fromkeys(detected))

        return detected, diagnostics


# ---------------------------------------------------------------------------
# 3) DEMO / TEST AREA
# ---------------------------------------------------------------------------

def _print_demo(user_input: str, extractor: EmbeddingSymptomExtractor, threshold: float) -> None:
    print(f"User said: '{user_input}'")

    detected, diag = extractor.analyze(user_input, threshold=threshold)

    # Print similarity scores so you can justify the threshold in defense.
    for m in sorted(diag, key=lambda x: x.symptom):
        print(f"  -> Similarity to {m.symptom}: {m.score:.4f} (best anchor: '{m.best_anchor}')")

    print("DETECTED:", detected)
    print("-" * 60)


if __name__ == "__main__":
    # You can tune this. Start at 0.50 and adjust based on false positives/negatives.
    # With more symptom-specific anchors, a stricter threshold reduces false positives.
    THRESHOLD = 0.65

    extractor = EmbeddingSymptomExtractor(SYMPTOM_ANCHORS)

    print("--- TEST 1: Direct Bisaya ---")
    _print_demo("grabe gi ubo jud ko", extractor, THRESHOLD)

    print("--- TEST 2: Slang/Conyo (not an exact dictionary phrase) ---")
    _print_demo("sobrang throbbing ng head ko", extractor, THRESHOLD)

    print("--- TEST 3: Multiple Symptoms ---")
    _print_demo("sakit ulo ko tapos inuubo", extractor, THRESHOLD)
