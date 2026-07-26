from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateDocument:
    candidate_id: str
    label: str
    text: str
    anchors: tuple[str, ...]


def load_symptom_candidate_corpus() -> list[CandidateDocument]:
    """Build a symptom-intent candidate corpus from the active Mendo data.

    The corpus contains approved symptom labels only. It is suitable for
    TF-IDF, embedding retrieval, and reranker experiments.
    """

    from mendo_core.step1 import SYMPTOM_DICTIONARY
    from mendo_core.step2 import SYMPTOM_ANCHORS

    labels = sorted(set(SYMPTOM_DICTIONARY) | set(SYMPTOM_ANCHORS))
    docs: list[CandidateDocument] = []
    for label in labels:
        phrases = list(SYMPTOM_DICTIONARY.get(label, []))
        anchors = list(SYMPTOM_ANCHORS.get(label, []))
        merged = list(dict.fromkeys([label.replace("_", " ").lower()] + phrases + anchors))
        docs.append(
            CandidateDocument(
                candidate_id=f"SYMPTOM:{label}",
                label=label,
                text=" ; ".join(merged),
                anchors=tuple(merged),
            )
        )
    return docs
