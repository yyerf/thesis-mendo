"""Benchmark semantic similarity models for thesis-ready comparison.

Compares:
- SentenceTransformer embedding models (MiniLM / MPNet / LaBSE by default)
- TF-IDF baseline (non-deep-learning)

Dataset format (JSONL):
  {"text1":"...","text2":"...","label":1}

Where label is:
- 1 => semantically similar (same symptom meaning)
- 0 => not similar

Example:
  python benchmarks/benchmark_semantic_models.py \
    --dataset data/datasets/st_pairs.sample.jsonl \
        --th-start 0.40 --th-stop 0.85 --th-step 0.05 \
    --out benchmarks/results/semantic_models_benchmark.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import psutil
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, average_precision_score, precision_recall_fscore_support, roc_auc_score
from sklearn.metrics.pairwise import cosine_similarity


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Reduce noisy third-party logs by default.
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


DEFAULT_MODELS: Dict[str, str] = {
    "MiniLM": "paraphrase-multilingual-MiniLM-L12-v2",
    "MPNet": "paraphrase-multilingual-mpnet-base-v2",
    "LaBSE": "sentence-transformers/LaBSE",
}


@dataclass
class PairExample:
    text1: str
    text2: str
    label: int


@dataclass
class BenchmarkRow:
    model: str
    kind: str
    n_examples: int
    threshold: float | None
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    average_precision: float | None
    total_time_sec: float
    avg_latency_ms: float
    pairs_per_sec: float
    memory_delta_mb: float
    error: str = ""


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _to_label(v: object) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return 1 if int(v) != 0 else 0
    s = str(v).strip().lower()
    return 1 if s in {"1", "true", "yes", "same", "similar"} else 0


def _resolve_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p

    # Prefer repo-root relative paths so defaults work from any CWD.
    root_relative = (ROOT_DIR / p).resolve()
    if root_relative.exists():
        return root_relative

    # Fallback to current-working-directory relative path.
    return p.resolve()


def load_pairs_jsonl(path: Path, limit: int | None = None) -> List[PairExample]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    out: List[PairExample] = []
    with path.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            obj = json.loads(line)
            t1 = str(obj.get("text1") or "").strip()
            t2 = str(obj.get("text2") or "").strip()
            if not t1 or not t2:
                raise ValueError(f"Line {i}: expected non-empty text1/text2")
            lbl = _to_label(obj.get("label", 0))
            out.append(PairExample(text1=t1, text2=t2, label=lbl))
            if limit is not None and len(out) >= limit:
                break

    if not out:
        raise ValueError(f"No usable examples in {path}")
    return out


def _binary_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> Tuple[float, float, float, float]:
    acc = float(accuracy_score(y_true, y_pred))
    p, r, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    return acc, float(p), float(r), float(f1)


def _score_metrics(y_true: Sequence[int], y_score: Sequence[float]) -> Tuple[float | None, float | None]:
    y_true_arr = np.asarray(y_true)
    y_score_arr = np.asarray(y_score)
    if len(np.unique(y_true_arr)) < 2:
        return None, None
    try:
        roc = float(roc_auc_score(y_true_arr, y_score_arr))
    except Exception:
        roc = None
    try:
        ap = float(average_precision_score(y_true_arr, y_score_arr))
    except Exception:
        ap = None
    return roc, ap


def _build_thresholds(start: float, stop: float, step: float) -> np.ndarray:
    if step <= 0:
        raise ValueError("--th-step must be > 0")
    if stop <= start:
        raise ValueError("--th-stop must be greater than --th-start")
    return np.arange(start, stop, step)


def _best_threshold_metrics(y_true: Sequence[int], scores: Sequence[float], thresholds: Sequence[float]) -> Tuple[float, float, float, float, float]:
    if len(thresholds) == 0:
        raise ValueError("No thresholds provided")

    best_threshold = float(thresholds[0])
    best_acc, best_p, best_r, best_f1 = -1.0, -1.0, -1.0, -1.0

    for t in thresholds:
        y_pred = [1 if float(s) >= float(t) else 0 for s in scores]
        acc, p, r, f1 = _binary_metrics(y_true, y_pred)
        if f1 > best_f1:
            best_threshold = float(t)
            best_acc, best_p, best_r, best_f1 = acc, p, r, f1

    return best_threshold, best_acc, best_p, best_r, best_f1


def benchmark_embedding_model(
    model_label: str,
    model_name: str,
    pairs: Sequence[PairExample],
    thresholds: Sequence[float],
    device: str,
    local_files_only: bool,
) -> BenchmarkRow:
    process = psutil.Process()
    mem_before = process.memory_info().rss / (1024**2)

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name, device=device, local_files_only=local_files_only)

        mem_loaded = process.memory_info().rss / (1024**2)

        text1 = [p.text1 for p in pairs]
        text2 = [p.text2 for p in pairs]
        y_true = [p.label for p in pairs]

        start = time.perf_counter()
        emb1 = model.encode(text1, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True)
        emb2 = model.encode(text2, convert_to_numpy=True, show_progress_bar=False, normalize_embeddings=True)

        # With normalized vectors, cosine similarity = dot product.
        sims = np.sum(emb1 * emb2, axis=1)
        best_t, acc, p, r, f1 = _best_threshold_metrics(y_true, sims, thresholds)
        elapsed = time.perf_counter() - start

        roc_auc, avg_precision = _score_metrics(y_true, sims)
        mem_after = process.memory_info().rss / (1024**2)

        n = len(pairs)
        return BenchmarkRow(
            model=model_label,
            kind="embedding",
            n_examples=n,
            threshold=best_t,
            accuracy=acc,
            precision=p,
            recall=r,
            f1=f1,
            roc_auc=roc_auc,
            average_precision=avg_precision,
            total_time_sec=elapsed,
            avg_latency_ms=_safe_div(elapsed * 1000.0, n),
            pairs_per_sec=_safe_div(n, elapsed),
            memory_delta_mb=max(mem_after - mem_before, mem_loaded - mem_before),
        )
    except Exception as e:
        n = len(pairs)
        return BenchmarkRow(
            model=model_label,
            kind="embedding",
            n_examples=n,
            threshold=None,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            roc_auc=None,
            average_precision=None,
            total_time_sec=0.0,
            avg_latency_ms=0.0,
            pairs_per_sec=0.0,
            memory_delta_mb=0.0,
            error=str(e),
        )


def benchmark_tfidf(pairs: Sequence[PairExample], thresholds: Sequence[float]) -> BenchmarkRow:
    process = psutil.Process()
    mem_before = process.memory_info().rss / (1024**2)

    text1 = [p.text1 for p in pairs]
    text2 = [p.text2 for p in pairs]
    y_true = [p.label for p in pairs]

    corpus = text1 + text2
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=1)

    start = time.perf_counter()
    vectorizer.fit(corpus)
    v1 = vectorizer.transform(text1)
    v2 = vectorizer.transform(text2)
    sims = cosine_similarity(v1, v2).diagonal()
    best_t, acc, p, r, f1 = _best_threshold_metrics(y_true, sims, thresholds)
    elapsed = time.perf_counter() - start

    roc_auc, avg_precision = _score_metrics(y_true, sims)
    mem_after = process.memory_info().rss / (1024**2)

    n = len(pairs)
    return BenchmarkRow(
        model="TF-IDF",
        kind="baseline",
        n_examples=n,
        threshold=best_t,
        accuracy=acc,
        precision=p,
        recall=r,
        f1=f1,
        roc_auc=roc_auc,
        average_precision=avg_precision,
        total_time_sec=elapsed,
        avg_latency_ms=_safe_div(elapsed * 1000.0, n),
        pairs_per_sec=_safe_div(n, elapsed),
        memory_delta_mb=max(0.0, mem_after - mem_before),
    )


def benchmark_rule_overlap(pairs: Sequence[PairExample]) -> BenchmarkRow:
    text1 = [p.text1 for p in pairs]
    text2 = [p.text2 for p in pairs]
    y_true = [p.label for p in pairs]

    start = time.perf_counter()
    try:
        from mendo_core.step1 import extract_symptoms as extract_step1

        y_pred: List[int] = []
        for a, b in zip(text1, text2):
            sa = set(extract_step1(a))
            sb = set(extract_step1(b))
            y_pred.append(1 if sa and sb and (sa == sb) else 0)
        elapsed = time.perf_counter() - start
        acc, p, r, f1 = _binary_metrics(y_true, y_pred)
        n = len(pairs)
        return BenchmarkRow(
            model="Rules-Step1",
            kind="baseline",
            n_examples=n,
            threshold=None,
            accuracy=acc,
            precision=p,
            recall=r,
            f1=f1,
            roc_auc=None,
            average_precision=None,
            total_time_sec=elapsed,
            avg_latency_ms=_safe_div(elapsed * 1000.0, n),
            pairs_per_sec=_safe_div(n, elapsed),
            memory_delta_mb=0.0,
        )
    except Exception as e:
        n = len(pairs)
        return BenchmarkRow(
            model="Rules-Step1",
            kind="baseline",
            n_examples=n,
            threshold=None,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1=0.0,
            roc_auc=None,
            average_precision=None,
            total_time_sec=0.0,
            avg_latency_ms=0.0,
            pairs_per_sec=0.0,
            memory_delta_mb=0.0,
            error=str(e),
        )


def _resolve_model_sources(model_root: str | None) -> Dict[str, str]:
    if not model_root:
        return dict(DEFAULT_MODELS)

    root = _resolve_path(model_root)
    if not root.exists():
        raise FileNotFoundError(f"Model root not found: {root}")

    return {
        "MiniLM": str(root / "paraphrase-multilingual-MiniLM-L12-v2"),
        "MPNet": str(root / "paraphrase-multilingual-mpnet-base-v2"),
        "LaBSE": str(root / "LaBSE"),
    }


def print_table(rows: Sequence[BenchmarkRow]) -> None:
    print("\n=== Semantic Similarity Benchmark ===")
    print(
        "{:<12} {:<10} {:>6} {:>7} {:>7} {:>7} {:>6} {:>7} {:>9} {:>11} {:>10}".format(
            "Model", "Type", "Acc", "Prec", "Rec", "F1", "Thr", "ROC", "ms/pair", "pairs/sec", "Mem(MB)"
        )
    )
    print("-" * 118)
    for r in rows:
        if r.error:
            print(f"{r.model:<12} ERROR: {r.error}")
            continue
        thr = "-" if r.threshold is None else f"{r.threshold:.2f}"
        roc = "-" if r.roc_auc is None else f"{r.roc_auc:.3f}"
        print(
            "{:<12} {:<10} {:>6.3f} {:>7.3f} {:>7.3f} {:>7.3f} {:>6} {:>7} {:>9.2f} {:>11.2f} {:>10.2f}".format(
                r.model,
                r.kind,
                r.accuracy,
                r.precision,
                r.recall,
                r.f1,
                thr,
                roc,
                r.avg_latency_ms,
                r.pairs_per_sec,
                r.memory_delta_mb,
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark embedding models vs TF-IDF for pair similarity")
    parser.add_argument(
        "--dataset",
        "--data",
        dest="dataset",
        type=str,
        default="data/datasets/st_pairs.sample.jsonl",
        help="JSONL pair dataset",
    )
    parser.add_argument("--th-start", type=float, default=0.40, help="Threshold sweep start (inclusive)")
    parser.add_argument("--th-stop", type=float, default=0.85, help="Threshold sweep stop (exclusive)")
    parser.add_argument("--th-step", type=float, default=0.05, help="Threshold sweep step")
    parser.add_argument("--limit", type=int, default=None, help="Use only first N samples")
    parser.add_argument("--skip-embeddings", action="store_true", help="Run TF-IDF only")
    parser.add_argument("--no-rule-baseline", action="store_true", help="Disable Step1 rule-overlap baseline")
    parser.add_argument("--device", type=str, default="cpu", choices=["cpu", "cuda"], help="Device for embedding models")
    parser.add_argument("--model-root", type=str, default="", help="Local folder containing model subfolders for MiniLM/MPNet/LaBSE")
    parser.add_argument("--local-only", action="store_true", help="Do not download from HF Hub; load models from local cache/path only")
    parser.add_argument("--out", type=str, default="", help="Optional output JSON path")
    args = parser.parse_args()

    dataset_path = _resolve_path(args.dataset)
    pairs = load_pairs_jsonl(dataset_path, limit=args.limit)
    thresholds = _build_thresholds(args.th_start, args.th_stop, args.th_step)
    model_sources = _resolve_model_sources(args.model_root or None)

    rows: List[BenchmarkRow] = []
    rows.append(benchmark_tfidf(pairs, thresholds=thresholds))

    if not args.no_rule_baseline:
        rows.append(benchmark_rule_overlap(pairs))

    if not args.skip_embeddings:
        for label, model_name in model_sources.items():
            rows.append(
                benchmark_embedding_model(
                    label,
                    model_name,
                    pairs,
                    thresholds=thresholds,
                    device=args.device,
                    local_files_only=args.local_only,
                )
            )

    print_table(rows)

    if args.out:
        out_path = _resolve_path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset": str(dataset_path),
            "threshold_sweep": {
                "start": args.th_start,
                "stop": args.th_stop,
                "step": args.th_step,
                "values": [float(x) for x in thresholds.tolist()],
            },
            "count": len(pairs),
            "results": [asdict(r) for r in rows],
        }
        out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved JSON report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
