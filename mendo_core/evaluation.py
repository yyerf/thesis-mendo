"""Dependency-free metrics for adjudicated multilabel clinical reviews."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, Iterable, List, Sequence, Set


def case_metrics(predicted: Iterable[str], expected: Iterable[str]) -> Dict[str, Any]:
    pred, gold = set(predicted), set(expected)
    tp, fp, fn = len(pred & gold), len(pred - gold), len(gold - pred)
    precision = tp / (tp + fp) if tp + fp else (1.0 if not gold else 0.0)
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "exact_match": pred == gold,
    }


def aggregate_metrics(cases: Sequence[Dict[str, Iterable[str]]]) -> Dict[str, Any]:
    rows = [case_metrics(c["predicted"], c["expected"]) for c in cases]
    tp = sum(r["true_positive"] for r in rows)
    fp = sum(r["false_positive"] for r in rows)
    fn = sum(r["false_negative"] for r in rows)
    micro_precision = tp / (tp + fp) if tp + fp else (1.0 if not fn else 0.0)
    micro_recall = tp / (tp + fn) if tp + fn else 1.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )

    labels: Set[str] = set()
    for c in cases:
        labels.update(c["predicted"])
        labels.update(c["expected"])
    label_f1: List[float] = []
    for label in sorted(labels):
        binary_cases = [
            {
                "predicted": [label] if label in set(c["predicted"]) else [],
                "expected": [label] if label in set(c["expected"]) else [],
            }
            for c in cases
        ]
        label_rows = [case_metrics(c["predicted"], c["expected"]) for c in binary_cases]
        ltp = sum(r["true_positive"] for r in label_rows)
        lfp = sum(r["false_positive"] for r in label_rows)
        lfn = sum(r["false_negative"] for r in label_rows)
        lp = ltp / (ltp + lfp) if ltp + lfp else (1.0 if not lfn else 0.0)
        lr = ltp / (ltp + lfn) if ltp + lfn else 1.0
        label_f1.append(2 * lp * lr / (lp + lr) if lp + lr else 0.0)

    return {
        "case_count": len(cases),
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_f1": sum(label_f1) / len(label_f1) if label_f1 else 0.0,
        "exact_match_rate": (
            sum(1 for row in rows if row["exact_match"]) / len(rows) if rows else None
        ),
    }


def clinical_appropriateness_rate(judgments: Iterable[str]) -> Dict[str, Any]:
    usable = [j for j in judgments if j in {"appropriate", "inappropriate"}]
    return {
        "judged_case_count": len(usable),
        "rate": usable.count("appropriate") / len(usable) if usable else None,
    }


def cohen_kappa(left: Sequence[Any], right: Sequence[Any]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Kappa requires two equally sized, non-empty rating lists")
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    values = set(left) | set(right)
    expected = sum(
        (left.count(v) / len(left)) * (right.count(v) / len(right)) for v in values
    )
    return 1.0 if expected == 1.0 else (observed - expected) / (1.0 - expected)


def multilabel_reviewer_kappa(reviews: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Average label-wise kappa over every reviewer pair's shared cases."""
    by_reviewer: Dict[Any, Dict[Any, Set[str]]] = defaultdict(dict)
    labels: Set[str] = set()
    for row in reviews:
        selected = set(row.get("expected_symptoms", []))
        by_reviewer[row["reviewer_id"]][row["interaction_id"]] = selected
        labels.update(selected)

    values: List[float] = []
    shared_case_count = 0
    for left_id, right_id in combinations(sorted(by_reviewer), 2):
        shared = sorted(set(by_reviewer[left_id]) & set(by_reviewer[right_id]))
        if not shared:
            continue
        shared_case_count += len(shared)
        pair_labels = labels | {
            label
            for case_id in shared
            for label in (
                by_reviewer[left_id][case_id] | by_reviewer[right_id][case_id]
            )
        }
        for label in pair_labels:
            left = [label in by_reviewer[left_id][case_id] for case_id in shared]
            right = [label in by_reviewer[right_id][case_id] for case_id in shared]
            values.append(cohen_kappa(left, right))

    if not values:
        return {
            "status": "insufficient_reviewers",
            "kappa": None,
            "reviewer_count": len(by_reviewer),
            "shared_case_count": shared_case_count,
        }
    return {
        "status": "available",
        "kappa": sum(values) / len(values),
        "reviewer_count": len(by_reviewer),
        "shared_case_count": shared_case_count,
    }
