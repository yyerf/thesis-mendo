"""Benchmark symptom-spotting models on a labeled dataset.

Dataset format: JSONL (one JSON object per line)
  {"id":"ex001","text":"...","labels":["cough","fever"]}

Metrics:
- exact_match_accuracy: % examples where predicted labels == true labels
- micro precision/recall/F1 over all (example,label) decisions
- hamming_accuracy: label-wise accuracy over the full label set
- per-label precision/recall/F1

Usage:
  python benchmark.py --dataset datasets/symptom_eval.sample.jsonl --model rules
  python benchmark.py --dataset datasets/symptom_eval.sample.jsonl --all-models
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from mendo_core.symptom_models import SYMPTOM_LABELS, available_models, get_model


@dataclass(frozen=True)
class Example:
    id: str
    text: str
    labels: Set[str]


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def load_jsonl_dataset(path: str) -> List[Example]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    examples: List[Example] = []
    with p.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i} of {path}") from e

            ex_id = str(obj.get("id") or f"line_{i}")
            text = str(obj.get("text") or "")
            labels_val = obj.get("labels")
            if not isinstance(labels_val, list):
                raise ValueError(f"Line {i} labels must be a list")

            labels = {str(x).strip() for x in labels_val if str(x).strip()}
            examples.append(Example(id=ex_id, text=text, labels=labels))

    if not examples:
        raise ValueError(f"No examples loaded from {path}")

    return examples


@dataclass
class AggregateCounts:
    tp: int = 0
    fp: int = 0
    fn: int = 0


@dataclass
class BenchmarkResult:
    model: str
    n_examples: int
    exact_match_accuracy: float
    hamming_accuracy: float
    micro_precision: float
    micro_recall: float
    micro_f1: float
    per_label: Dict[str, Dict[str, float]]
    mismatches: List[Dict[str, object]]


def compute_metrics(
    y_true: Sequence[Set[str]],
    y_pred: Sequence[Set[str]],
    label_universe: Sequence[str],
) -> Tuple[float, float, float, float, float, Dict[str, Dict[str, float]]]:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred length mismatch")

    n = len(y_true)
    exact = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    exact_match_accuracy = _safe_div(exact, n)

    # micro counts
    micro = AggregateCounts()
    for t, p in zip(y_true, y_pred):
        micro.tp += len(t & p)
        micro.fp += len(p - t)
        micro.fn += len(t - p)

    micro_precision = _safe_div(micro.tp, micro.tp + micro.fp)
    micro_recall = _safe_div(micro.tp, micro.tp + micro.fn)
    micro_f1 = _safe_div(2 * micro_precision * micro_recall, micro_precision + micro_recall)

    # Hamming accuracy across fixed label universe
    total_decisions = n * len(label_universe)
    correct = 0
    for t, p in zip(y_true, y_pred):
        for lbl in label_universe:
            correct += int((lbl in t) == (lbl in p))
    hamming_accuracy = _safe_div(correct, total_decisions)

    # Per-label metrics
    per_label: Dict[str, Dict[str, float]] = {}
    for lbl in label_universe:
        tp = sum(1 for t, p in zip(y_true, y_pred) if (lbl in t) and (lbl in p))
        fp = sum(1 for t, p in zip(y_true, y_pred) if (lbl not in t) and (lbl in p))
        fn = sum(1 for t, p in zip(y_true, y_pred) if (lbl in t) and (lbl not in p))
        prec = _safe_div(tp, tp + fp)
        rec = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * prec * rec, prec + rec)
        per_label[lbl] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn}

    return exact_match_accuracy, hamming_accuracy, micro_precision, micro_recall, micro_f1, per_label


def run_benchmark(
    dataset: List[Example],
    model_id: str,
    show_mismatches: int = 0,
    limit: Optional[int] = None,
) -> BenchmarkResult:
    model = get_model(model_id)

    data = dataset[: limit if limit is not None else len(dataset)]
    y_true: List[Set[str]] = []
    y_pred: List[Set[str]] = []
    mismatches: List[Dict[str, object]] = []

    for ex in data:
        pred = set(model.predict(ex.text))
        true = set(ex.labels)
        y_true.append(true)
        y_pred.append(pred)

        if show_mismatches and pred != true and len(mismatches) < show_mismatches:
            mismatches.append(
                {
                    "id": ex.id,
                    "text": ex.text,
                    "true": sorted(true),
                    "pred": sorted(pred),
                    "missing": sorted(true - pred),
                    "extra": sorted(pred - true),
                }
            )

    exact, hamming, mp, mr, mf1, per_label = compute_metrics(y_true, y_pred, SYMPTOM_LABELS)

    return BenchmarkResult(
        model=model.name,
        n_examples=len(data),
        exact_match_accuracy=exact,
        hamming_accuracy=hamming,
        micro_precision=mp,
        micro_recall=mr,
        micro_f1=mf1,
        per_label=per_label,
        mismatches=mismatches,
    )


def _format_pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def print_result(res: BenchmarkResult, top_labels: int = 0) -> None:
    print(f"MODEL: {res.model}")
    print(f"EXAMPLES: {res.n_examples}")
    print(f"EXACT MATCH ACCURACY: {_format_pct(res.exact_match_accuracy)}")
    print(f"HAMMING ACCURACY:     {_format_pct(res.hamming_accuracy)}")
    print(
        "MICRO: "
        f"P={_format_pct(res.micro_precision)} "
        f"R={_format_pct(res.micro_recall)} "
        f"F1={_format_pct(res.micro_f1)}"
    )

    if top_labels:
        # show worst F1 labels
        rows = sorted(((lbl, m["f1"], m["tp"], m["fp"], m["fn"]) for lbl, m in res.per_label.items()), key=lambda r: r[1])
        print(f"\nWORST {min(top_labels, len(rows))} LABELS (by F1):")
        for lbl, f1, tp, fp, fn in rows[:top_labels]:
            print(f"- {lbl}: F1={_format_pct(float(f1))} (tp={tp} fp={fp} fn={fn})")

    if res.mismatches:
        print("\nMISMATCHES:")
        for m in res.mismatches:
            print(f"- {m['id']}: true={m['true']} pred={m['pred']} missing={m['missing']} extra={m['extra']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark symptom spotting models")
    parser.add_argument("--dataset", type=str, required=True, help="Path to JSONL dataset")
    parser.add_argument("--model", type=str, default="rules", help=f"Model id (available: {', '.join(available_models())})")
    parser.add_argument("--all-models", action="store_true", help="Run all available models")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    parser.add_argument("--show-mismatches", type=int, default=5, help="Print up to N mismatches (0 disables)")
    parser.add_argument("--limit", type=int, default=None, help="Only evaluate first N examples")
    parser.add_argument("--top-labels", type=int, default=0, help="Show worst N labels by F1")

    args = parser.parse_args()

    dataset = load_jsonl_dataset(args.dataset)

    model_ids = available_models() if args.all_models else [args.model]
    results = [run_benchmark(dataset, mid, show_mismatches=args.show_mismatches, limit=args.limit) for mid in model_ids]

    if args.json:
        print(
            json.dumps(
                {
                    "dataset": args.dataset,
                    "results": [
                        {
                            "model": r.model,
                            "n_examples": r.n_examples,
                            "exact_match_accuracy": r.exact_match_accuracy,
                            "hamming_accuracy": r.hamming_accuracy,
                            "micro_precision": r.micro_precision,
                            "micro_recall": r.micro_recall,
                            "micro_f1": r.micro_f1,
                            "per_label": r.per_label,
                            "mismatches": r.mismatches,
                        }
                        for r in results
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for idx, r in enumerate(results):
            if idx:
                print("\n" + ("-" * 60) + "\n")
            print_result(r, top_labels=args.top_labels)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
