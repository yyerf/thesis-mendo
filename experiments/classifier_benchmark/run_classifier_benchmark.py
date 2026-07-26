#!/usr/bin/env python3
"""Comparative classifier benchmark for MendoVendo v3.0 (Table 10).

Compares the deployed Mendo pipeline against trained baselines on the SAME
288-case multilabel detection benchmark (testing/benchmark/testing.csv):

  - Mendo Dictionary (Stage 1)        : evaluated cold on all 288 (no training)
  - Mendo Hybrid (deployed)           : evaluated cold on all 288 (raw output)
  - SVM (TF-IDF char n-grams)         : 5-fold stratified CV
  - Logistic Regression (TF-IDF)      : 5-fold stratified CV
  - Random Forest (TF-IDF)            : 5-fold stratified CV
  - mBERT  (bert-base-multilingual)   : fine-tuned, 5-fold CV (multilabel head)
  - XLM-RoBERTa (xlm-roberta-base)    : fine-tuned, 5-fold CV (multilabel head)

The task is multilabel over 13 symptom labels; "NONE" = the empty label set.
Mendo is evaluated cold (no training) on all 288; the trainable baselines use
5-fold CV (~230 train / 58 test per fold), so the baselines actually train on
~80% of the data while Mendo never sees it. This mirrors the methodology
described in the thesis. Metrics: exact-match accuracy (set equality, the
primary metric), micro precision/recall/F1, and Hamming loss.

CPU-only by design (the dev GPU is sm_61, unsupported by current torch).

Usage:
  python run_classifier_benchmark.py --models svm,logreg,rf,mendo
  python run_classifier_benchmark.py --models mbert,xlmr        # slow (CPU)
  python run_classifier_benchmark.py --models all
"""
import os, sys, json, csv, argparse, time
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")        # force CPU (GPU is sm_61)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", str(os.cpu_count() or 8))

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, REPO)
CSV_PATH = os.path.join(REPO, "testing", "benchmark", "testing.csv")
RESULTS_DIR = os.path.join(HERE, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

SEED = 42
N_FOLDS = 5
LABELS = [
    "FEVER", "HEADACHE", "BODY_ACHES", "RASHES", "STOMACH_ACHE", "SORE_THROAT",
    "COUGH_PRODUCTIVE", "ALLERGIC_RHINITIS", "COUGH_GENERAL", "COUGH_DRY",
    "DIARRHEA", "NASAL_CONGESTION", "RUNNY_NOSE",
]
LAB2I = {l: i for i, l in enumerate(LABELS)}


def load_data():
    texts, Y = [], []
    with open(CSV_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            texts.append((r["input_text"] or "").strip())
            vec = np.zeros(len(LABELS), dtype=np.int8)
            for part in (r["expected_symptoms"] or "").split(","):
                p = part.strip()
                if p and p != "NONE" and p in LAB2I:
                    vec[LAB2I[p]] = 1
            Y.append(vec)
    return texts, np.array(Y)


# ── metrics ─────────────────────────────────────────────────────────────────
def metrics(Y_true, Y_pred):
    Y_true = np.asarray(Y_true); Y_pred = np.asarray(Y_pred)
    exact = float(np.mean(np.all(Y_true == Y_pred, axis=1)))
    tp = int(np.sum((Y_true == 1) & (Y_pred == 1)))
    fp = int(np.sum((Y_true == 0) & (Y_pred == 1)))
    fn = int(np.sum((Y_true == 1) & (Y_pred == 0)))
    micro_p = tp / (tp + fp) if (tp + fp) else 0.0
    micro_r = tp / (tp + fn) if (tp + fn) else 0.0
    micro_f1 = 2 * micro_p * micro_r / (micro_p + micro_r) if (micro_p + micro_r) else 0.0
    hamming = float(np.mean(Y_true != Y_pred))
    n = len(Y_true)
    return {
        "exact_matches": int(round(exact * n)), "total": n,
        "accuracy": round(exact, 4),
        "micro_precision": round(micro_p, 4), "micro_recall": round(micro_r, 4),
        "micro_f1": round(micro_f1, 4), "hamming_loss": round(hamming, 4),
    }


def strat_key(Y):
    """Single-label stratification key for multilabel CV (primary label index,
    or -1 for NONE)."""
    keys = []
    for row in Y:
        idx = np.where(row == 1)[0]
        keys.append(int(idx[0]) if len(idx) else -1)
    return np.array(keys)


def make_folds(Y):
    try:
        from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
        mskf = MultilabelStratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
        return list(mskf.split(np.zeros(len(Y)), Y)), "MultilabelStratifiedKFold"
    except Exception:
        from sklearn.model_selection import StratifiedKFold, KFold
        key = strat_key(Y)
        # StratifiedKFold needs >=N_FOLDS members per class; fall back if not
        from collections import Counter
        if min(Counter(key).values()) >= N_FOLDS:
            skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
            return list(skf.split(np.zeros(len(Y)), key)), "StratifiedKFold(primary-label)"
        kf = KFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
        return list(kf.split(np.zeros(len(Y)))), "KFold(shuffle)"


# ── Mendo (no training, cold on all 288) ────────────────────────────────────
def eval_mendo():
    from mendo_core.step1 import extract_symptoms
    from mendo_core.prediction_pipeline import predict_symptoms
    texts, Y = load_data()
    out = {}
    # dictionary-only (Stage 1)
    Yp_dict = np.zeros_like(Y)
    for i, t in enumerate(texts):
        for s in extract_symptoms(t):
            if s in LAB2I:
                Yp_dict[i, LAB2I[s]] = 1
    out["mendo_dictionary"] = {"display": "Mendo Dictionary (Stage 1)", **metrics(Y, Yp_dict),
                               "trained": False}
    # hybrid deployed (raw output, no clarification override)
    Yp_hyb = np.zeros_like(Y)
    for i, t in enumerate(texts):
        for s in predict_symptoms(t).get("final", {}).get("symptoms", []):
            if s in LAB2I:
                Yp_hyb[i, LAB2I[s]] = 1
    out["mendo_hybrid"] = {"display": "Mendo Hybrid Pipeline (raw)", **metrics(Y, Yp_hyb),
                           "trained": False}
    return out


# ── sklearn TF-IDF baselines (5-fold CV) ────────────────────────────────────
def eval_sklearn(model_name):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.svm import LinearSVC
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.multiclass import OneVsRestClassifier
    texts, Y = load_data()
    folds, fold_name = make_folds(Y)
    Yp = np.zeros_like(Y)
    for tr, te in folds:
        Xtr = [texts[i] for i in tr]; Xte = [texts[i] for i in te]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), max_features=10000)
        Xtr_v = vec.fit_transform(Xtr); Xte_v = vec.transform(Xte)
        if model_name == "svm":
            clf = OneVsRestClassifier(LinearSVC(C=1.0, random_state=SEED))
        elif model_name == "logreg":
            clf = OneVsRestClassifier(LogisticRegression(max_iter=1000, random_state=SEED))
        elif model_name == "rf":
            clf = OneVsRestClassifier(RandomForestClassifier(n_estimators=200, random_state=SEED, n_jobs=-1))
        else:
            raise ValueError(model_name)
        # drop all-zero label columns within this train fold to avoid degenerate fits
        clf.fit(Xtr_v, Y[tr])
        pred = clf.predict(Xte_v)
        Yp[te] = np.asarray(pred)
    disp = {"svm": "SVM (TF-IDF char)", "logreg": "Logistic Regression (TF-IDF)",
            "rf": "Random Forest (TF-IDF)"}[model_name]
    return {model_name: {"display": disp, **metrics(Y, Yp), "trained": True, "cv": fold_name}}


# ── transformer baselines (fine-tuned, 5-fold CV, CPU) ──────────────────────
def eval_transformer(hf_name, disp, max_len=128, epochs=10, bs=16, lr=5e-5):
    import torch
    from torch.utils.data import DataLoader, TensorDataset
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    torch.manual_seed(SEED)
    torch.set_num_threads(os.cpu_count() or 8)            # use all CPU cores
    device = torch.device("cpu")
    texts, Y = load_data()
    folds, fold_name = make_folds(Y)
    Yp = np.zeros_like(Y)
    tok = AutoTokenizer.from_pretrained(hf_name)
    import copy
    # Load the heavy weights ONCE; reset to this initial state each fold (avoids
    # reloading ~0.7-1.1 GB from disk 5x, which was the real bottleneck).
    base = AutoModelForSequenceClassification.from_pretrained(
        hf_name, num_labels=len(LABELS), problem_type="multi_label_classification").to(device)
    init_state = copy.deepcopy(base.state_dict())
    for fi, (tr, te) in enumerate(folds):
        enc_tr = tok([texts[i] for i in tr], truncation=True, padding="max_length",
                     max_length=max_len, return_tensors="pt")
        enc_te = tok([texts[i] for i in te], truncation=True, padding="max_length",
                     max_length=max_len, return_tensors="pt")
        ytr = torch.tensor(Y[tr], dtype=torch.float32)
        ds = TensorDataset(enc_tr["input_ids"], enc_tr["attention_mask"], ytr)
        dl = DataLoader(ds, batch_size=bs, shuffle=True)
        model = base
        model.load_state_dict(init_state)            # reset to identical start each fold
        opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
        model.train()
        for ep in range(epochs):
            for ids, mask, yb in dl:
                opt.zero_grad()
                out = model(input_ids=ids.to(device), attention_mask=mask.to(device), labels=yb.to(device))
                out.loss.backward(); opt.step()
        model.eval()
        with torch.no_grad():
            logits = model(input_ids=enc_te["input_ids"].to(device),
                           attention_mask=enc_te["attention_mask"].to(device)).logits
            pred = (torch.sigmoid(logits) >= 0.5).int().cpu().numpy()
        Yp[te] = pred
        print(f"    [{disp}] fold {fi+1}/{N_FOLDS} done", flush=True)
    key = "mbert" if "bert-base-multilingual" in hf_name else "xlmr"
    return {key: {"display": disp, **metrics(Y, Yp), "trained": True, "cv": fold_name}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="svm,logreg,rf,mendo")
    args = ap.parse_args()
    want = [m.strip() for m in args.models.split(",") if m.strip()]
    if "all" in want:
        want = ["mendo", "svm", "logreg", "rf", "mbert", "xlmr"]

    results = {}
    t0 = time.time()
    if "mendo" in want:
        print("Evaluating Mendo (cold, all 288)..."); results.update(eval_mendo())
    for m in ("svm", "logreg", "rf"):
        if m in want:
            print(f"Training {m} (5-fold CV)..."); results.update(eval_sklearn(m))
    if "mbert" in want:
        print("Fine-tuning mBERT (5-fold CV, CPU)...")
        results.update(eval_transformer("bert-base-multilingual-cased", "mBERT (fine-tuned)"))
    if "xlmr" in want:
        print("Fine-tuning XLM-RoBERTa (5-fold CV, CPU)...")
        results.update(eval_transformer("xlm-roberta-base", "XLM-RoBERTa (fine-tuned)"))

    elapsed = round(time.time() - t0, 1)
    payload = {"dataset": CSV_PATH, "n": 288, "n_folds": N_FOLDS, "seed": SEED,
               "labels": LABELS, "elapsed_sec": elapsed, "models": results}
    out_path = os.path.join(RESULTS_DIR, f"classifier_results_{'-'.join(want)}.json")
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\n{'model':34} {'exact':>11} {'micro-F1':>9} {'hamming':>8}")
    order = sorted(results.items(), key=lambda kv: -kv[1]["accuracy"])
    for k, m in order:
        print(f"{m['display']:34} {str(m['exact_matches'])+'/288':>7} ({m['accuracy']*100:4.1f}%) "
              f"{m['micro_f1']:>9.3f} {m['hamming_loss']:>8.3f}")
    print(f"\nElapsed: {elapsed}s  ->  {out_path}")


if __name__ == "__main__":
    main()
