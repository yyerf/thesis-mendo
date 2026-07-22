from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_predictions_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = [
        "model_id",
        "test_id",
        "category",
        "language",
        "text",
        "expected",
        "predicted",
        "exact",
        "precision",
        "recall",
        "f1",
        "missed",
        "extra",
        "source",
        "latency_ms",
        "red_flags",
        "recommendation_action",
        "recommendations",
        "error",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "model_id": row["model_id"],
                    "test_id": row["test_id"],
                    "category": row["category"],
                    "language": row.get("language", "unspecified"),
                    "text": row["text"],
                    "expected": ",".join(sorted(row["expected"])),
                    "predicted": ",".join(sorted(row["predicted"])),
                    "exact": row["exact"],
                    "precision": row["precision"],
                    "recall": row["recall"],
                    "f1": row["f1"],
                    "missed": ",".join(sorted(row["missed"])),
                    "extra": ",".join(sorted(row["extra"])),
                    "source": row["source"],
                    "latency_ms": row["latency_ms"],
                    "red_flags": ",".join(row.get("red_flags", [])),
                    "recommendation_action": row.get("recommendation_action", ""),
                    "recommendations": ",".join(row.get("recommendations", [])),
                    "error": row.get("error", ""),
                    "notes": row.get("notes", ""),
                }
            )


def write_markdown_report(path: Path, summary: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Mendo Retrieval Benchmark Report")
    lines.append("")
    lines.append(f"Dataset: `{summary['dataset']}`")
    lines.append(f"Clarification simulation: `{summary['apply_clarification']}`")
    lines.append("")
    lines.append("## Model Summary")
    lines.append("")
    lines.append("| Model | Accuracy | Micro F1 | Macro F1 | p95 ms | Red-flag OTC leaks |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for model_id, model_summary in summary["models"].items():
        if model_summary.get("unavailable"):
            lines.append(f"| {model_id} | unavailable | unavailable | unavailable | unavailable | unavailable |")
            continue
        lines.append(
            "| {model} | {acc:.1f}% | {micro:.3f} | {macro:.3f} | {p95:.1f} | {leaks} |".format(
                model=model_id,
                acc=float(model_summary["accuracy"]) * 100.0,
                micro=float(model_summary["micro_f1"]),
                macro=float(model_summary["macro_f1"]),
                p95=float(model_summary["latency_ms"]["p95"]),
                leaks=int(model_summary["red_flag_otc_leakage"]),
            )
        )

    lines.append("")
    lines.append("## Language Breakdown")
    for model_id, model_summary in summary["models"].items():
        if model_summary.get("unavailable"):
            continue
        lines.append("")
        lines.append(f"### {model_id}")
        lines.append("")
        lines.append("| Language | Total | Accuracy | Avg F1 | Failures |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for language, stat in sorted(model_summary.get("language_stats", {}).items()):
            lines.append(
                f"| {language} | {stat['total']} | {float(stat['accuracy']) * 100:.1f}% | "
                f"{float(stat['avg_f1']):.3f} | {stat['failures']} |"
            )

    lines.append("")
    lines.append("## Category Breakdown")
    for model_id, model_summary in summary["models"].items():
        if model_summary.get("unavailable"):
            continue
        lines.append("")
        lines.append(f"### {model_id}")
        lines.append("")
        lines.append("| Category | Total | Accuracy | Avg F1 | Failures |")
        lines.append("| --- | ---: | ---: | ---: | ---: |")
        for category, stat in sorted(model_summary["category_stats"].items()):
            lines.append(
                f"| {category} | {stat['total']} | {float(stat['accuracy']) * 100:.1f}% | "
                f"{float(stat['avg_f1']):.3f} | {stat['failures']} |"
            )

    lines.append("")
    lines.append("## Top Failures")
    for model_id, failures in summary.get("top_failures", {}).items():
        lines.append("")
        lines.append(f"### {model_id}")
        if not failures:
            lines.append("")
            lines.append("No failures in the displayed sample.")
            continue
        for failure in failures:
            lines.append("")
            lines.append(f"- Test `{failure['test_id']}` ({failure['category']}): {failure['text']}")
            lines.append(f"  Expected: `{', '.join(sorted(failure['expected'])) or 'NONE'}`")
            lines.append(f"  Predicted: `{', '.join(sorted(failure['predicted'])) or 'NONE'}`")
            if failure.get("missed"):
                lines.append(f"  Missed: `{', '.join(sorted(failure['missed']))}`")
            if failure.get("extra"):
                lines.append(f"  Extra: `{', '.join(sorted(failure['extra']))}`")

    lines.append("")
    lines.append("## Thesis Interpretation Notes")
    lines.append("")
    lines.append("- Raw NLP mode is better for pure model comparison.")
    lines.append("- Clarification simulation is better for evaluating the full kiosk workflow.")
    lines.append("- Red-flag OTC leakage must remain zero for any acceptable model.")
    lines.append("- A model with higher F1 but worse safety consistency should not be selected.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
