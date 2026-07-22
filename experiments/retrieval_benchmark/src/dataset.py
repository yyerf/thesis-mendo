from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class BenchmarkExample:
    test_id: str
    text: str
    expected_labels: frozenset[str]
    category: str
    age: int | None = None
    cough_type: str = ""
    notes: str = ""
    language: str = "unspecified"


def split_labels(raw: str) -> frozenset[str]:
    labels = {
        part.strip().upper()
        for part in str(raw or "").split(",")
        if part.strip()
    }
    if "NONE" in labels:
        return frozenset()
    return frozenset(labels)


def load_benchmark_csv(path: str | Path, *, limit: int = 0) -> list[BenchmarkExample]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {p}")

    examples: list[BenchmarkExample] = []
    with p.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            age: int | None
            try:
                age = int(str(row.get("age") or "").strip())
            except ValueError:
                age = None

            examples.append(
                BenchmarkExample(
                    test_id=str(row.get("test_id") or len(examples) + 1),
                    text=str(row.get("input_text") or row.get("text") or "").strip(),
                    expected_labels=split_labels(str(row.get("expected_symptoms") or row.get("labels") or "")),
                    category=str(row.get("test_category") or row.get("category") or "uncategorized").strip(),
                    age=age,
                    cough_type=str(row.get("cough_type") or "").strip(),
                    notes=str(row.get("notes") or "").strip(),
                    language=str(row.get("language") or "unspecified").strip() or "unspecified",
                )
            )
            if limit and len(examples) >= limit:
                break

    if not examples:
        raise ValueError(f"No examples loaded from {p}")
    return examples


def label_universe(examples: Iterable[BenchmarkExample]) -> list[str]:
    labels: set[str] = set()
    for ex in examples:
        labels.update(ex.expected_labels)
    return sorted(labels)

