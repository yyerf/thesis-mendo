from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from .corpus import CandidateDocument, load_symptom_candidate_corpus


COUGH_LABELS = {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}


@dataclass
class ModelPrediction:
    labels: set[str]
    scores: dict[str, float] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    error: str = ""


class BenchmarkAdapter(Protocol):
    model_id: str
    display_name: str

    def predict(self, text: str) -> ModelPrediction:
        ...


def apply_cough_clarification(labels: set[str], cough_type: str) -> set[str]:
    ctype = str(cough_type or "").strip().lower()
    mapped = None
    if ctype in {"dry", "dry_cough", "walang", "walay"}:
        mapped = "COUGH_DRY"
    elif ctype in {"productive", "wet", "with_phlegm", "plema"}:
        mapped = "COUGH_PRODUCTIVE"
    if not mapped:
        return set(labels)

    out = {label for label in labels if label not in COUGH_LABELS}
    out.add(mapped)
    return out


class DictionaryAdapter:
    model_id = "dictionary"
    display_name = "Deterministic Dictionary"

    def predict(self, text: str) -> ModelPrediction:
        from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=False,
        )
        final = report.get("final", {})
        stage = next((s for s in report.get("stages", []) if s.get("stage") == "dictionary"), {})
        evidence = []
        for row in stage.get("details", []) or []:
            evidence.append(
                {
                    "label": row.get("symptom"),
                    "matched_phrases": row.get("matched_phrases", []),
                    "stage": "dictionary",
                }
            )
        return ModelPrediction(
            labels=set(final.get("symptoms", []) or []),
            evidence=evidence,
            source=str(final.get("source") or "dictionary"),
        )


class CurrentHybridAdapter:
    model_id = "current_hybrid"
    display_name = "Current Dictionary + MiniLM Fallback"

    def predict(self, text: str) -> ModelPrediction:
        from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
        final = report.get("final", {})
        evidence = []
        for stage in report.get("stages", []):
            if stage.get("stage") == "dictionary":
                for row in stage.get("details", []) or []:
                    evidence.append(
                        {
                            "label": row.get("symptom"),
                            "matched_phrases": row.get("matched_phrases", []),
                            "stage": "dictionary",
                        }
                    )
            elif stage.get("stage") == "semantic":
                for row in stage.get("scores", [])[:5]:
                    evidence.append(
                        {
                            "label": row.get("symptom"),
                            "score": row.get("score"),
                            "best_anchor": row.get("best_anchor"),
                            "stage": "semantic",
                        }
                    )
        return ModelPrediction(
            labels=set(final.get("symptoms", []) or []),
            evidence=evidence,
            source=str(final.get("source") or "current_hybrid"),
        )


class TfidfCosineAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        display_name: str,
        analyzer: str,
        ngram_range: tuple[int, int],
        threshold: float,
        top_k: int,
        docs: list[CandidateDocument] | None = None,
    ) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        self.model_id = model_id
        self.display_name = display_name
        self.threshold = threshold
        self.top_k = top_k
        self.docs = docs or load_symptom_candidate_corpus()
        self._cosine_similarity = cosine_similarity
        self._vectorizer = TfidfVectorizer(
            analyzer=analyzer,
            ngram_range=ngram_range,
            lowercase=True,
            strip_accents=None,
            sublinear_tf=True,
        )
        self._doc_matrix = self._vectorizer.fit_transform([doc.text for doc in self.docs])

    def predict(self, text: str) -> ModelPrediction:
        q = self._vectorizer.transform([text])
        sims = self._cosine_similarity(q, self._doc_matrix)[0]
        ranked = sorted(enumerate(sims), key=lambda item: float(item[1]), reverse=True)
        labels: set[str] = set()
        scores: dict[str, float] = {}
        evidence: list[dict[str, Any]] = []
        for idx, raw_score in ranked[: self.top_k]:
            score = float(raw_score)
            doc = self.docs[idx]
            scores[doc.label] = score
            evidence.append(
                {
                    "label": doc.label,
                    "score": score,
                    "stage": "tfidf",
                    "candidate_id": doc.candidate_id,
                }
            )
            if score >= self.threshold:
                labels.add(doc.label)
        return ModelPrediction(labels=labels, scores=scores, evidence=evidence, source=self.model_id)


class TfidfHybridAdapter:
    def __init__(self, *, threshold: float = 0.20, top_k: int = 3) -> None:
        docs = load_symptom_candidate_corpus()
        self.model_id = "tfidf_hybrid"
        self.display_name = "TF-IDF Word+Char Cosine"
        self.threshold = threshold
        self.top_k = top_k
        self.word = TfidfCosineAdapter(
            model_id="tfidf_word_inner",
            display_name="word",
            analyzer="word",
            ngram_range=(1, 2),
            threshold=0.0,
            top_k=len(docs),
            docs=docs,
        )
        self.char = TfidfCosineAdapter(
            model_id="tfidf_char_inner",
            display_name="char",
            analyzer="char_wb",
            ngram_range=(3, 5),
            threshold=0.0,
            top_k=len(docs),
            docs=docs,
        )
        self.docs = docs

    def predict(self, text: str) -> ModelPrediction:
        word_pred = self.word.predict(text)
        char_pred = self.char.predict(text)
        scores: dict[str, float] = {}
        for doc in self.docs:
            scores[doc.label] = max(word_pred.scores.get(doc.label, 0.0), char_pred.scores.get(doc.label, 0.0))
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)[: self.top_k]
        labels = {label for label, score in ranked if score >= self.threshold}
        evidence = [
            {"label": label, "score": score, "stage": "tfidf_hybrid"}
            for label, score in ranked
        ]
        return ModelPrediction(labels=labels, scores=dict(ranked), evidence=evidence, source=self.model_id)


class SentenceTransformerEmbeddingAdapter:
    def __init__(
        self,
        *,
        model_id: str,
        display_name: str,
        model_name: str,
        threshold: float = 0.45,
        top_k: int = 3,
        query_prefix: str = "",
        query_prompt_name: str | None = None,
        document_prompt_name: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.display_name = display_name
        self.model_name = model_name
        self.threshold = threshold
        self.top_k = top_k
        self.query_prefix = query_prefix
        self.query_prompt_name = query_prompt_name
        self.document_prompt_name = document_prompt_name
        self.docs = load_symptom_candidate_corpus()

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("sentence-transformers is not installed") from exc

        device = os.getenv("MENDO_BENCH_DEVICE", "cpu")
        try:
            self.model = SentenceTransformer(model_name, trust_remote_code=True, device=device)
        except TypeError:
            self.model = SentenceTransformer(model_name, device=device)

        doc_encode_kwargs: dict[str, Any] = {
            "normalize_embeddings": True,
            "show_progress_bar": False,
        }
        if self.document_prompt_name:
            doc_encode_kwargs["prompt_name"] = self.document_prompt_name
        self.doc_embeddings = self.model.encode([doc.text for doc in self.docs], **doc_encode_kwargs)

    def predict(self, text: str) -> ModelPrediction:
        query = f"{self.query_prefix}{text}" if self.query_prefix else text
        query_encode_kwargs: dict[str, Any] = {
            "normalize_embeddings": True,
            "show_progress_bar": False,
        }
        if self.query_prompt_name:
            query_encode_kwargs["prompt_name"] = self.query_prompt_name
        q_emb = self.model.encode([query], **query_encode_kwargs)[0]
        sims = self.doc_embeddings @ q_emb
        ranked = sorted(enumerate(sims), key=lambda item: float(item[1]), reverse=True)[: self.top_k]
        labels: set[str] = set()
        scores: dict[str, float] = {}
        evidence: list[dict[str, Any]] = []
        for idx, raw_score in ranked:
            score = float(raw_score)
            if math.isnan(score):
                score = 0.0
            doc = self.docs[idx]
            scores[doc.label] = score
            evidence.append(
                {
                    "label": doc.label,
                    "score": score,
                    "stage": "embedding",
                    "candidate_id": doc.candidate_id,
                    "model": self.model_name,
                }
            )
            if score >= self.threshold:
                labels.add(doc.label)
        return ModelPrediction(labels=labels, scores=scores, evidence=evidence, source=self.model_id)


class CrossEncoderRerankAdapter:
    def __init__(
        self,
        *,
        retriever: SentenceTransformerEmbeddingAdapter,
        model_id: str = "minilm_qwen3_rerank",
        display_name: str = "MiniLM Retrieval + Qwen3 Reranker",
        reranker_name: str = "Qwen/Qwen3-Reranker-0.6B",
        threshold: float = 0.0,
        top_k: int = 3,
    ) -> None:
        self.model_id = model_id
        self.display_name = display_name
        self.retriever = retriever
        self.reranker_name = reranker_name
        self.threshold = threshold
        self.top_k = top_k

        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("sentence-transformers CrossEncoder is not available") from exc

        try:
            self.reranker = CrossEncoder(reranker_name, trust_remote_code=True)
        except TypeError:
            self.reranker = CrossEncoder(reranker_name)

    def predict(self, text: str) -> ModelPrediction:
        retrieved = self.retriever.predict(text)
        candidate_labels = [row["label"] for row in retrieved.evidence[: max(self.top_k, 10)]]
        docs = [doc for doc in self.retriever.docs if doc.label in candidate_labels]
        pairs = [(text, doc.text) for doc in docs]
        raw_scores = self.reranker.predict(pairs) if pairs else []
        scored = sorted(zip(docs, raw_scores), key=lambda item: float(item[1]), reverse=True)[: self.top_k]
        labels = {doc.label for doc, score in scored if float(score) >= self.threshold}
        scores = {doc.label: float(score) for doc, score in scored}
        evidence = [
            {
                "label": doc.label,
                "score": float(score),
                "stage": "reranker",
                "candidate_id": doc.candidate_id,
                "model": self.reranker_name,
            }
            for doc, score in scored
        ]
        return ModelPrediction(labels=labels, scores=scores, evidence=evidence, source=self.model_id)


def build_adapter(model_id: str, *, threshold: float | None = None, top_k: int | None = None) -> BenchmarkAdapter:
    mid = model_id.strip().lower()
    if mid == "dictionary":
        return DictionaryAdapter()
    if mid == "current_hybrid":
        return CurrentHybridAdapter()
    if mid == "tfidf_word":
        return TfidfCosineAdapter(
            model_id="tfidf_word",
            display_name="TF-IDF Word Cosine",
            analyzer="word",
            ngram_range=(1, 2),
            threshold=threshold if threshold is not None else 0.16,
            top_k=top_k or 3,
        )
    if mid == "tfidf_char":
        return TfidfCosineAdapter(
            model_id="tfidf_char",
            display_name="TF-IDF Char Cosine",
            analyzer="char_wb",
            ngram_range=(3, 5),
            threshold=threshold if threshold is not None else 0.20,
            top_k=top_k or 3,
        )
    if mid == "tfidf_hybrid":
        return TfidfHybridAdapter(threshold=threshold if threshold is not None else 0.20, top_k=top_k or 3)
    if mid == "minilm":
        return SentenceTransformerEmbeddingAdapter(
            model_id="minilm",
            display_name="MiniLM Multilingual Embedding",
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            threshold=threshold if threshold is not None else 0.45,
            top_k=top_k or 3,
        )
    if mid == "qwen3_embedding_0_6b":
        return SentenceTransformerEmbeddingAdapter(
            model_id="qwen3_embedding_0_6b",
            display_name="Qwen3 Embedding 0.6B",
            model_name="Qwen/Qwen3-Embedding-0.6B",
            threshold=threshold if threshold is not None else 0.40,
            top_k=top_k or 3,
            query_prompt_name="query",
            document_prompt_name="document",
        )
    if mid == "bge_m3":
        return SentenceTransformerEmbeddingAdapter(
            model_id="bge_m3",
            display_name="BGE-M3 Embedding",
            model_name="BAAI/bge-m3",
            threshold=threshold if threshold is not None else 0.40,
            top_k=top_k or 3,
        )
    if mid == "jina_v3":
        return SentenceTransformerEmbeddingAdapter(
            model_id="jina_v3",
            display_name="Jina Embeddings v3",
            model_name="jinaai/jina-embeddings-v3",
            threshold=threshold if threshold is not None else 0.40,
            top_k=top_k or 3,
            query_prompt_name="retrieval.query",
            document_prompt_name="retrieval.passage",
        )
    if mid == "minilm_qwen3_rerank":
        retriever = SentenceTransformerEmbeddingAdapter(
            model_id="minilm",
            display_name="MiniLM Multilingual Embedding",
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            threshold=0.0,
            top_k=top_k or 10,
        )
        return CrossEncoderRerankAdapter(
            retriever=retriever,
            threshold=threshold if threshold is not None else 0.0,
            top_k=min(top_k or 3, 5),
        )
    raise ValueError(f"Unknown model id: {model_id}")


def timed_predict(adapter: BenchmarkAdapter, text: str) -> tuple[ModelPrediction, float]:
    start = time.perf_counter()
    pred = adapter.predict(text)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return pred, elapsed_ms
