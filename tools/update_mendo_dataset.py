"""Update data/Mendo-Datasets.json from data/Mendo-Datasets-latest.json.

Why this exists
- The app historically reads data/Mendo-Datasets.json and expects a "Minimum Age" column.
- Newer exports may include "Age Group" instead and may contain NaN values.

This tool:
- loads the latest JSON
- normalizes NaN -> ""
- infers a numeric-ish "Minimum Age" from "Age Group"
- writes a strict JSON file (no NaN) to the target path

Run:
  python tools/update_mendo_dataset.py \
    --latest data/Mendo-Datasets-latest.json \
    --out data/Mendo-Datasets.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List


def _is_nan(x: Any) -> bool:
    return isinstance(x, float) and math.isnan(x)


def _infer_min_age(age_group: Any) -> Any:
    if age_group is None or _is_nan(age_group):
        return ""

    if isinstance(age_group, (int, float)) and not isinstance(age_group, bool):
        try:
            return int(age_group)
        except Exception:
            return str(age_group)

    s = str(age_group).strip().lower()
    if not s:
        return ""

    if any(k in s for k in ("all ages", "any age", "everyone")):
        return "All ages"

    if "month" in s or "months" in s or "infant" in s:
        return 0

    plus = re.findall(r"(\d+)\s*\+\s*(?:years|year|yo)?", s)
    if plus:
        return min(int(x) for x in plus)

    ranges = re.findall(r"(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:years|year|yo)", s)
    if ranges:
        return min(int(a) for (a, _b) in ranges)

    nums = re.findall(r"(\d+)", s)
    if nums:
        return min(int(x) for x in nums)

    if "adult" in s and "adolescent" not in s:
        return 18

    return ""


def _clean(obj: Any) -> Any:
    if _is_nan(obj):
        return ""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Update Mendo-Datasets.json from latest export")
    ap.add_argument("--latest", default="data/Mendo-Datasets-latest.json", help="Input latest dataset JSON")
    ap.add_argument("--out", default="data/Mendo-Datasets.json", help="Output path for app dataset JSON")
    args = ap.parse_args()

    latest_path = Path(args.latest)
    out_path = Path(args.out)

    if not latest_path.exists():
        raise SystemExit(f"Latest dataset not found: {latest_path}")

    raw = json.loads(latest_path.read_text(encoding="utf-8"))
    raw = _clean(raw)

    rows = raw.get("Sheet1")
    if not isinstance(rows, list):
        raise SystemExit("Expected top-level key 'Sheet1' to be a list")

    updated: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue

        # Ensure Minimum Age exists for the app's age-gating.
        if r.get("Minimum Age") in (None, ""):
            r["Minimum Age"] = _infer_min_age(r.get("Age Group"))

        updated.append(r)

    out_obj = {"Sheet1": updated}

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote updated dataset to: {out_path}")
    print(f"Rows: {len(updated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
