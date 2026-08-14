"""DEV-ONLY experiment: chunked semantic scoring vs whole-text scoring.

Question (2026-08-14 brainstorm): does scoring sentence fragments independently
(conjunction chunking) recover more symptoms than whole-text scoring, without
breaking negation / precision-first guards?

Design safety: the lexical guard + negation safety filters ALWAYS run on the
FULL text, never per-chunk, so "wala akong lagnat at ubo" can never yield
FEVER/COUGH from a bare "ubo" chunk.

This script only measures. It does not modify the pipeline.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mendo_core.step3_hybrid import (
    _apply_semantic_safety_filters,
    _get_semantic_extractor,
    _semantic_lexical_guard,
    detect_red_flags,
    extract_symptoms_dictionary,
)

CONJUNCTIONS = (
    "tapos", "unya", "unya", "at", "ug", "and", "pero", "tsaka",
    "saka", "pagkatapos", "then", "tas", "sabay", "pagka", "diri",
)

_SPLIT_RX = re.compile(
    r"[,.!?;]|"
    r"\b(" + "|".join(CONJUNCTIONS) + r")\b(?=\s[A-Za-z])",
    re.IGNORECASE,
)


def split_chunks(text: str) -> list[str]:
    parts = _SPLIT_RX.split(text)
    out: list[str] = []
    for p in parts:
        p = (p or "").strip()
        if not p:
            continue
        if p.lower() in CONJUNCTIONS or len(p) < 3:
            continue
        out.append(p)
    return out


def classify(text: str) -> set[str]:
    sem, _ext = _get_semantic_extractor().analyze(text, threshold=0.65)
    return set(sem)


def guarded(text: str, labels: set[str]) -> set[str]:
    labels = set(_semantic_lexical_guard(text, labels))
    labels, _ = _apply_semantic_safety_filters(
        text, labels, red_flags=detect_red_flags(text)
    )
    return set(labels)


def whole(text: str) -> set[str]:
    return guarded(text, classify(text))


def chunked(text: str) -> set[str]:
    labels: set[str] = set()
    for c in split_chunks(text):
        labels |= classify(c)
    return guarded(text, labels)


def norm(s: str) -> str:
    return s.strip().upper().replace(" ", "_")


def main() -> int:
    ext = _get_semantic_extractor()
    print(f"backend: {type(ext).__name__}")

    print("\n=== 16 PARAPHRASES ===")
    gen = [
        json.loads(l)
        for l in (ROOT / "testing/benchmark/semantic_generalization.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    w_correct = c_correct = 0
    for g in gen:
        exp = {norm(e) for e in g["expected"]}
        w = whole(g["text"])
        c = chunked(g["text"])
        wc, cc = w == exp, c == exp
        w_correct += wc
        c_correct += cc
        flag = " *FLIP*" if cc and not wc else (" *BROKE*" if wc and not cc else "")
        print(f"{'Y' if cc else 'n'}{'Y' if wc else 'n'} | {g['text'][:58]:<60} | exp={sorted(exp)}")
        print(f"      whole={sorted(w)} chunk={sorted(c)} chunks={split_chunks(g['text'])}{flag}")
    print(f"whole={w_correct}/16  chunked={c_correct}/16")

    print("\n=== 20 FRESH NEGATIVES (must stay clean) ===")
    neg = [
        json.loads(l)
        for l in (ROOT / "testing/benchmark/semantic_fresh_negatives.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    w_neg = c_neg = 0
    for g in neg:
        w, c = whole(g["text"]), chunked(g["text"])
        w_neg += w == set()
        c_neg += c == set()
        if c:
            print(f"  CHUNK FIRED: {g['text'][:60]} {sorted(c)}")
    print(f"whole clean={w_neg}/20  chunked clean={c_neg}/20")

    print("\n=== 288 zero-dict rows (must stay NONE) ===")
    rows = list(csv.DictReader(open(ROOT / "testing/benchmark/testing.csv", encoding="utf-8-sig")))
    zero_rows = [r for r in rows if not extract_symptoms_dictionary(r["input_text"])]
    fired = 0
    for r in zero_rows:
        c = chunked(r["input_text"])
        if c:
            fired += 1
            print(f"  CHUNK FIRED: {r['input_text'][:60]} {sorted(c)} | exp={r['expected_symptoms']}")
    print(f"chunked fired on {fired}/{len(zero_rows)} zero-dict rows")

    print("\n=== exact-dict rows: would chunked enrichment add spurious? ===")
    def norm_set(s: str) -> set[str]:
        return {norm(e) for e in s.replace(";", ",").split(",") if e.strip()}
    exact = [r for r in rows if set(extract_symptoms_dictionary(r["input_text"])) == norm_set(r["expected_symptoms"])]
    spurious = 0
    for r in exact:
        c = chunked(r["input_text"])
        if c - norm_set(r["expected_symptoms"]):
            spurious += 1
            print(f"  SPURIOUS: {r['input_text'][:60]} | exp={r['expected_symptoms']} | chunk={sorted(c - norm_set(r['expected_symptoms']))}")
    print(f"spurious additions on {spurious}/{len(exact)} exact-dict rows")

    print("\n=== AI EXAMPLE (dict partial hit) ===")
    t = "luod kaayo akong paminaw parang may sinat ako tapos sige ra kug ubo"
    print(f"dict={extract_symptoms_dictionary(t)}")
    print(f"whole={sorted(whole(t))}  chunked={sorted(chunked(t))}")
    print(f"chunks={split_chunks(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())