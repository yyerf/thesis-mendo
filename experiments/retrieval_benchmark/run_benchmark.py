#!/usr/bin/env python3
"""Run isolated Mendo retrieval benchmarks.

This script intentionally lives outside the production Flask app. It imports
the current Mendo core as a baseline and compares alternative retrieval
adapters without modifying runtime behavior.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from experiments.retrieval_benchmark.src.runner import run_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Mendo symptom retrieval models")
    parser.add_argument(
        "--dataset",
        default="testing/benchmark/testing.csv",
        help="CSV dataset path with the current Mendo benchmark format",
    )
    parser.add_argument(
        "--models",
        default="dictionary,tfidf_word,tfidf_char",
        help=(
            "Comma-separated model ids. Available: dictionary,current_hybrid,"
            "tfidf_word,tfidf_char,tfidf_hybrid,minilm,qwen3_embedding_0_6b,"
            "bge_m3,jina_v3,minilm_qwen3_rerank"
        ),
    )
    parser.add_argument("--limit", type=int, default=0, help="Evaluate only the first N rows")
    parser.add_argument(
        "--apply-clarification",
        action="store_true",
        help="Simulate cough clarification answers from the cough_type CSV column",
    )
    parser.add_argument("--threshold", type=float, default=None, help="Override model score threshold where supported")
    parser.add_argument("--top-k", type=int, default=None, help="Override top-k where supported")
    parser.add_argument(
        "--out-dir",
        default="experiments/retrieval_benchmark/results",
        help="Directory where run outputs are written",
    )
    parser.add_argument(
        "--no-recommendations",
        action="store_true",
        help="Skip recommendation action evaluation",
    )
    args = parser.parse_args()
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
