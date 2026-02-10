"""Fine-tune a SentenceTransformer for this project.

What this trains:
- Step 2 semantic encoder (used in mendo_core/step2.py)

Why:
- Improves semantic matching of local Tagalog/Bisaya slang, typos, and paraphrases.

Input dataset format (JSONL), one per line:
  {"text1": "...", "text2": "...", "label": 1}

Where:
- Saves to an output directory; then point the runtime to it:
    export MENDO_SENTENCE_TRANSFORMER_MODEL=models/mendo-miniLM-finetuned

Install:
  python -m pip install sentence-transformers torch

Run:
  python tools/train_sentence_transformer.py \
    --train data/datasets/st_pairs.sample.jsonl \
    --out models/mendo-miniLM-finetuned \
    --epochs 1
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List, Tuple


def _iter_jsonl(path: str) -> Iterable[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    with p.open("r", encoding="utf-8") as f:
        for i, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i}: {path}") from e
            if not isinstance(obj, dict):
                continue
            yield obj


def load_pairs(path: str, limit: int | None = None) -> List[Tuple[str, str, float]]:
    pairs: List[Tuple[str, str, float]] = []
    for obj in _iter_jsonl(path):
        t1 = str(obj.get("text1") or "").strip()
        t2 = str(obj.get("text2") or "").strip()
        label = obj.get("label")
        if not t1 or not t2:
            continue
        try:
            y = float(label)
        except Exception:
            continue
        y = 1.0 if y >= 0.5 else 0.0
        pairs.append((t1, t2, y))
        if limit is not None and len(pairs) >= limit:
            break

    if not pairs:
        raise ValueError("No usable pairs found. Expected keys: text1, text2, label")

    return pairs


def main() -> int:
    ap = argparse.ArgumentParser(description="Fine-tune SentenceTransformer for semantic symptom matching")
    ap.add_argument("--base-model", default="paraphrase-multilingual-MiniLM-L12-v2", help="Base model name")
    ap.add_argument("--train", required=True, help="Training JSONL path (text1/text2/label)")
    ap.add_argument("--out", required=True, help="Output directory for fine-tuned model")
    ap.add_argument("--epochs", type=int, default=1, help="Epochs")
    ap.add_argument("--batch-size", type=int, default=16, help="Batch size")
    ap.add_argument("--warmup-steps", type=int, default=100, help="Warmup steps")
    ap.add_argument("--limit", type=int, default=None, help="Optional limit of training pairs")
    args = ap.parse_args()

    pairs = load_pairs(args.train, limit=args.limit)

    # Local imports so the repo can still run without torch installed.
    from torch.utils.data import DataLoader  # type: ignore
    from sentence_transformers import SentenceTransformer, InputExample, losses  # type: ignore

    model = SentenceTransformer(args.base_model)

    train_examples = [InputExample(texts=[t1, t2], label=y) for (t1, t2, y) in pairs]
    train_loader = DataLoader(train_examples, shuffle=True, batch_size=args.batch_size)

    # Simple and stable for 0/1 similarity labels.
    train_loss = losses.CosineSimilarityLoss(model)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model.fit(
        train_objectives=[(train_loader, train_loss)],
        epochs=max(1, int(args.epochs)),
        warmup_steps=max(0, int(args.warmup_steps)),
        show_progress_bar=True,
        output_path=str(out_dir),
    )

    print(f"Saved fine-tuned model to: {out_dir}")
    print("Use it with:")
    print(f"  export MENDO_SENTENCE_TRANSFORMER_MODEL={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
