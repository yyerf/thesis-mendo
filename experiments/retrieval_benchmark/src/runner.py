from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from .adapters import apply_cough_clarification, build_adapter, timed_predict
from .dataset import label_universe, load_benchmark_csv
from .metrics import evaluate_labels, summarize_predictions
from .reporting import write_json, write_markdown_report, write_predictions_csv


class RecommendationEvaluator:
    """Cached wrapper around the production deterministic recommendation path."""

    def __init__(self, *, skip: bool) -> None:
        self.skip = skip
        self.available = False
        self.error = ""
        self.detect_red_flags = None
        self.extract_conditions = None
        self.recommend_from_dataset = None
        self.rows = []

        if self.skip:
            return

        try:
            from mendo_core.step3_hybrid import detect_red_flags
            from mendo_core.step4_recommend import DATASET_DEFAULT, load_mendo_dataset, recommend_from_dataset
            from mendo_core.step1 import extract_conditions

            self.detect_red_flags = detect_red_flags
            self.extract_conditions = extract_conditions
            self.recommend_from_dataset = recommend_from_dataset
            self.rows = load_mendo_dataset(DATASET_DEFAULT)
            self.available = True
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    def snapshot(self, labels: set[str], text: str) -> tuple[str, list[str], list[str]]:
        if self.skip:
            return "not_run", [], []
        if not self.available:
            return f"error:{self.error}", [], []

        assert self.detect_red_flags is not None
        assert self.extract_conditions is not None
        assert self.recommend_from_dataset is not None

        try:
            red_flags = self.detect_red_flags(text)
            rec = self.recommend_from_dataset(
                sorted(labels),
                self.rows,
                red_flags=red_flags,
                user_input=text,
                detected_conditions=self.extract_conditions(text),
            )
            brands = [str(r.get("brand") or "") for r in rec.get("recommendations", []) if r.get("brand")]
            flag_names = [str(row.get("flag") or "") for row in red_flags]
            return str(rec.get("action") or "unknown"), brands, flag_names
        except Exception as exc:
            return f"error:{type(exc).__name__}", [], []


def _recommendation_snapshot(labels: set[str], text: str, evaluator: RecommendationEvaluator) -> tuple[str, list[str], list[str]]:
    return evaluator.snapshot(labels, text)


def evaluate_model(
    *,
    model_id: str,
    examples,
    labels: list[str],
    threshold: float | None,
    top_k: int | None,
    apply_clarification: bool,
    recommendation_evaluator: RecommendationEvaluator,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str] | None]:
    try:
        adapter = build_adapter(model_id, threshold=threshold, top_k=top_k)
    except Exception as exc:
        return {}, [], {"model_id": model_id, "reason": f"{type(exc).__name__}: {exc}"}

    rows: list[dict[str, Any]] = []
    for ex in examples:
        try:
            pred, latency_ms = timed_predict(adapter, ex.text)
        except Exception as exc:
            pred = None
            latency_ms = 0.0
            predicted = set()
            error = f"{type(exc).__name__}: {exc}"
            source = "error"
        else:
            predicted = set(pred.labels)
            error = pred.error
            source = pred.source

        if apply_clarification:
            predicted = apply_cough_clarification(predicted, ex.cough_type)

        metric = evaluate_labels(set(ex.expected_labels), predicted)
        action, recs, red_flags = _recommendation_snapshot(predicted, ex.text, recommendation_evaluator)

        rows.append(
            {
                "model_id": getattr(adapter, "model_id", model_id),
                "display_name": getattr(adapter, "display_name", model_id),
                "test_id": ex.test_id,
                "category": ex.category,
                "language": ex.language,
                "text": ex.text,
                "expected": set(ex.expected_labels),
                "predicted": predicted,
                "exact": metric.exact,
                "precision": round(metric.precision, 4),
                "recall": round(metric.recall, 4),
                "f1": round(metric.f1, 4),
                "correct": metric.correct,
                "missed": metric.missed,
                "extra": metric.extra,
                "source": source,
                "latency_ms": round(latency_ms, 3),
                "red_flags": red_flags,
                "recommendation_action": action,
                "recommendations": recs,
                "error": error,
                "notes": ex.notes,
            }
        )

    summary = summarize_predictions(examples=examples, rows=rows, label_universe=labels)
    summary["display_name"] = getattr(adapter, "display_name", model_id)
    return summary, rows, None


def run_cli(args) -> int:
    dataset_path = Path(args.dataset)
    if not dataset_path.is_absolute():
        dataset_path = Path.cwd() / dataset_path

    examples = load_benchmark_csv(dataset_path, limit=int(args.limit or 0))
    labels = label_universe(examples)
    model_ids = [m.strip() for m in str(args.models).split(",") if m.strip()]
    recommendation_evaluator = RecommendationEvaluator(skip=bool(args.no_recommendations))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out = Path(args.out_dir)
    if not base_out.is_absolute():
        base_out = Path.cwd() / base_out
    run_dir = base_out / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "timestamp": timestamp,
        "dataset": str(dataset_path),
        "example_count": len(examples),
        "apply_clarification": bool(args.apply_clarification),
        "models": {},
        "unavailable_models": [],
        "top_failures": {},
    }
    all_rows: list[dict[str, Any]] = []

    for model_id in model_ids:
        print(f"[benchmark] Running {model_id} on {len(examples)} examples...")
        model_summary, rows, unavailable = evaluate_model(
            model_id=model_id,
            examples=examples,
            labels=labels,
            threshold=args.threshold,
            top_k=args.top_k,
            apply_clarification=bool(args.apply_clarification),
            recommendation_evaluator=recommendation_evaluator,
        )
        if unavailable:
            print(f"[benchmark] Skipping {model_id}: {unavailable['reason']}")
            summary["models"][model_id] = {"unavailable": True, "reason": unavailable["reason"]}
            summary["unavailable_models"].append(unavailable)
            continue

        summary["models"][model_id] = model_summary
        failures = [row for row in rows if not row["exact"]][:10]
        summary["top_failures"][model_id] = [
            {
                "test_id": row["test_id"],
                "category": row["category"],
                "text": row["text"],
                "expected": sorted(row["expected"]),
                "predicted": sorted(row["predicted"]),
                "missed": sorted(row["missed"]),
                "extra": sorted(row["extra"]),
            }
            for row in failures
        ]
        all_rows.extend(rows)
        print(
            "[benchmark] {model}: accuracy={acc:.1f}% micro_f1={f1:.3f} p95={p95:.1f}ms leaks={leaks}".format(
                model=model_id,
                acc=float(model_summary["accuracy"]) * 100.0,
                f1=float(model_summary["micro_f1"]),
                p95=float(model_summary["latency_ms"]["p95"]),
                leaks=int(model_summary["red_flag_otc_leakage"]),
            )
        )

    write_json(run_dir / "summary.json", summary)
    write_predictions_csv(run_dir / "predictions.csv", all_rows)
    write_markdown_report(run_dir / "report.md", summary)

    print(f"[benchmark] Wrote {run_dir / 'summary.json'}")
    print(f"[benchmark] Wrote {run_dir / 'predictions.csv'}")
    print(f"[benchmark] Wrote {run_dir / 'report.md'}")
    return 0
