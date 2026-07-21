from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from .dataset import BenchmarkExample


@dataclass
class ExampleMetrics:
    exact: bool
    precision: float
    recall: float
    f1: float
    correct: set[str]
    missed: set[str]
    extra: set[str]


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def evaluate_labels(expected: set[str], predicted: set[str]) -> ExampleMetrics:
    if not expected and not predicted:
        return ExampleMetrics(True, 1.0, 1.0, 1.0, set(), set(), set())
    correct = expected & predicted
    missed = expected - predicted
    extra = predicted - expected
    precision = safe_div(len(correct), len(predicted))
    recall = safe_div(len(correct), len(expected))
    f1 = safe_div(2 * precision * recall, precision + recall)
    return ExampleMetrics(
        exact=expected == predicted,
        precision=precision,
        recall=recall,
        f1=f1,
        correct=correct,
        missed=missed,
        extra=extra,
    )


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    return float(ordered[max(0, min(idx, len(ordered) - 1))])


def summarize_predictions(
    *,
    examples: list[BenchmarkExample],
    rows: list[dict[str, Any]],
    label_universe: list[str],
) -> dict[str, Any]:
    total = len(rows)
    exact = sum(1 for row in rows if row["exact"])
    avg_precision = safe_div(sum(float(row["precision"]) for row in rows), total)
    avg_recall = safe_div(sum(float(row["recall"]) for row in rows), total)
    avg_f1 = safe_div(sum(float(row["f1"]) for row in rows), total)

    tp = fp = fn = 0
    for row in rows:
        tp += len(row["correct"])
        fp += len(row["extra"])
        fn += len(row["missed"])
    micro_p = safe_div(tp, tp + fp)
    micro_r = safe_div(tp, tp + fn)
    micro_f1 = safe_div(2 * micro_p * micro_r, micro_p + micro_r)

    per_label: dict[str, dict[str, float | int]] = {}
    for label in label_universe:
        l_tp = l_fp = l_fn = 0
        for row in rows:
            expected = set(row["expected"])
            predicted = set(row["predicted"])
            l_tp += int(label in expected and label in predicted)
            l_fp += int(label not in expected and label in predicted)
            l_fn += int(label in expected and label not in predicted)
        p = safe_div(l_tp, l_tp + l_fp)
        r = safe_div(l_tp, l_tp + l_fn)
        f1 = safe_div(2 * p * r, p + r)
        per_label[label] = {
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "tp": l_tp,
            "fp": l_fp,
            "fn": l_fn,
        }

    category_stats: dict[str, dict[str, Any]] = {}
    for ex, row in zip(examples, rows):
        stat = category_stats.setdefault(
            ex.category,
            {"total": 0, "exact": 0, "avg_f1": 0.0, "failures": 0},
        )
        stat["total"] += 1
        stat["exact"] += int(row["exact"])
        stat["avg_f1"] += float(row["f1"])
        stat["failures"] += int(not row["exact"])
    for stat in category_stats.values():
        stat["avg_f1"] = round(safe_div(float(stat["avg_f1"]), int(stat["total"])), 4)
        stat["accuracy"] = round(safe_div(int(stat["exact"]), int(stat["total"])), 4)

    language_stats: dict[str, dict[str, Any]] = {}
    for ex, row in zip(examples, rows):
        language = ex.language or "unspecified"
        stat = language_stats.setdefault(
            language,
            {"total": 0, "exact": 0, "avg_f1": 0.0, "failures": 0},
        )
        stat["total"] += 1
        stat["exact"] += int(row["exact"])
        stat["avg_f1"] += float(row["f1"])
        stat["failures"] += int(not row["exact"])
    for stat in language_stats.values():
        stat["avg_f1"] = round(safe_div(float(stat["avg_f1"]), int(stat["total"])), 4)
        stat["accuracy"] = round(safe_div(int(stat["exact"]), int(stat["total"])), 4)

    latencies = [float(row["latency_ms"]) for row in rows]
    recommendation_actions: dict[str, int] = {}
    safety_leaks = 0
    red_flag_cases = 0
    for row in rows:
        action = str(row.get("recommendation_action") or "not_run")
        recommendation_actions[action] = recommendation_actions.get(action, 0) + 1
        if row.get("red_flags"):
            red_flag_cases += 1
            if action == "recommend":
                safety_leaks += 1

    return {
        "total": total,
        "exact_matches": exact,
        "accuracy": round(safe_div(exact, total), 4),
        "avg_precision": round(avg_precision, 4),
        "avg_recall": round(avg_recall, 4),
        "avg_f1": round(avg_f1, 4),
        "micro_precision": round(micro_p, 4),
        "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(safe_div(sum(float(v["f1"]) for v in per_label.values()), len(per_label)), 4)
        if per_label
        else 0.0,
        "latency_ms": {
            "mean": round(safe_div(sum(latencies), len(latencies)), 3),
            "median": round(float(median(latencies)), 3) if latencies else 0.0,
            "p95": round(percentile(latencies, 95), 3),
            "max": round(max(latencies), 3) if latencies else 0.0,
        },
        "per_label": per_label,
        "category_stats": category_stats,
        "language_stats": language_stats,
        "recommendation_actions": recommendation_actions,
        "red_flag_cases": red_flag_cases,
        "red_flag_otc_leakage": safety_leaks,
    }
