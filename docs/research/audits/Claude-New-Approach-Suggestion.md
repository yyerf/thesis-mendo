# Claude — New-Approach Analysis for MendoVendo v3.0

**Question you asked:** Given your hard constraints (fully **offline**, **fast**, **POS-style kiosk** on a **Raspberry Pi 5 / no GPU**, multilingual Filipino input) — and given how much NLP/AI tech moved in 2025–2026 — is your current approach still the best one, or is there something better?

**Scope note:** Your thesis is already submitted, so treat everything here as **Iteration-2/3 future work**, not a criticism of what you defended. Your submitted approach is sound and defensible. This is about how to make the *next* version meaningfully better without breaking your constraints.

---

## TL;DR — the honest verdict

1. **Your *architecture* is still the right one — arguably more defensible in 2026, not less.** Keeping every safety-critical decision deterministic and using ML only for *language understanding* is exactly how serious clinical-decision-support systems are built. **Do not touch the Stage-4 safety engine. Do not let any model decide medicine.** New LLM tech changes nothing about that.

2. **But your specific language-understanding component is the weak link, and it's now outdated.** Your own benchmark proves it: on raw output the **dictionary alone (80.6%) beats the full hybrid (79.5%)** — meaning the MiniLM anchor-cosine fallback is currently *subtracting* value. That's the one part worth modernizing.

3. **The right modernization is NOT "add an LLM to the kiosk."** A chatbot-style generative model is the wrong tool for an offline, fast kiosk. The right move is subtler and stronger:

   > **Use a large LLM at *development* time to generate a big, realistic, labeled Filipino symptom corpus, then distill it into a small fine-tuned encoder *classifier* that runs in <100 ms on your Pi, fully offline.**

   This fixes your *two* real problems at once — the underperforming semantic layer **and** the data scarcity that sank your Table-10 transformers — while keeping you offline, fast, and safe.

**One-line answer:** *Right foundation, aging NLU implementation, clear and feasible upgrade path. You don't need a new architecture; you need to replace the brittle dictionary + anchor-cosine front-end with an LLM-distilled small classifier.*

---

## 1. Your design envelope (why most "2026 AI" is irrelevant to you)

| Constraint | Consequence |
|---|---|
| **Offline / low-connectivity** | No cloud APIs (GPT-4o, Claude, Gemini). Permanently. |
| **Raspberry Pi 5, no usable GPU** | CPU-only inference. Anything that needs a GPU at *inference* is out. |
| **Fast / kiosk UX** | Token-by-token *generation* is marginal; a single forward pass is ideal. |
| **Privacy (RA 10173)** | Data must stay on-device — reinforces offline. |
| **Safety-critical** | The recommendation engine must stay deterministic and auditable. |
| **Multilingual, code-switched, noisy** | Tag/Bis/Eng/Taglish/Jejemon + misspellings — the *hard* part. |
| **Narrow domain** | 13 symptom labels, 24 medicines. Tiny, fixed output space. |

The single most important consequence: **anything that needs the cloud, a GPU at inference, or long generative output is ruled out or marginal.** That eliminates ~90 % of 2026's AI headlines (cloud LLMs, agents, big RAG). That's *fine* — your task genuinely doesn't need them. The narrowness of your problem is your advantage, not a limitation.

---

## 2. What to KEEP (these are timeless and still correct in 2026)

- **The deterministic Stage-4 safety engine** (age filter, contraindications, duration thresholds, paracetamol/opposing-mechanism checks, red-flag suppression). This is the heart of the system and the strongest part of your defense. No 2026 technology improves on hard-coded rules for *safety guarantees* — LLMs make this *worse*, not better.
- **Stage-0 red-flag triage** (proximity + exclusion rules). Keep.
- **Precision-first philosophy** (a false positive is worse than a missed secondary symptom). Keep.
- **Offline-first / on-device**. Keep — it's now a selling point, not a handicap.
- **A fast lexical first pass.** Keep a dictionary, but demote it from "the brain" to "a high-precision shortcut" (see §6).

## 3. What to CHANGE (the genuine weak links)

- **The MiniLM anchor-cosine fallback (Stage 2).** Nearest-anchor cosine similarity with ~118 hand-written anchor sentences is a 2019-era technique and your weakest component. It only fires when the dictionary is empty, and when it does it mostly adds false positives (your dictionary-beats-hybrid result). This is the thing to replace.
- **The hand-maintained dictionary as the *primary* detector.** 331 phrases + fuzzy collision-exclusion lists is a maintenance treadmill that will never generalize to genuinely novel phrasings ("para he overflowing", "murag gisunog akong tiyan"). It's great as a *shortcut*, brittle as a *brain*.
- **The data-scarcity ceiling.** Your 288 LLM-written cases are too few to train anything. This is the real reason your Table-10 transformers failed — and it's now the easiest problem to fix.

---

## 4. The lesson your Table 10 *actually* teaches (and the 2026 plot twist)

Your Table 10 concluded: *"fine-tuned transformers underperform → rule-based wins."* That conclusion was **correct for your data, but wrong as a general lesson** — and in 2026 it flips.

The real cause of XLM-RoBERTa's 22.6 % wasn't the architecture. It was **~230 training examples spread over a 2¹³ = 8,192-way label space.** Starve any neural model and it collapses.

**The 2026 plot twist:** the bottleneck was never the model — it was *labeled data*, and capable LLMs now make labeled data nearly free. Generate **10k–50k** diverse, realistic, labeled Filipino kiosk inputs with a strong model, and a *small* fine-tuned encoder will **beat both your dictionary and your anchor-cosine fallback** — while staying tiny enough to run on the Pi. The thing that made rules win (no data) is exactly the thing 2026 tech removes.

This is the single most important idea in this document.

---

## 5. The 2026 option space, filtered through *your* constraints

| Approach | Offline on Pi 5? | Latency (Pi CPU) | Accuracy ceiling | Auditable? | Verdict for you |
|---|---|---|---|---|---|
| Cloud LLM (GPT/Claude/Gemini) | ❌ No | n/a | very high | ❌ | **Excluded** (offline + RA 10173) |
| Local generative LLM 7B+ (quantized) | ⚠️ Barely fits, very slow | ~seconds–minutes | high | ⚠️ | **No** — too slow/heavy for a kiosk |
| Small local LLM 0.5–1.7B + constrained JSON | ✅ Yes | ~1–4 s | medium-high | ⚠️ | **Maybe** — flexible NLU, but slow; fallback only (§7) |
| **Fine-tuned small *encoder classifier* (distilled)** | ✅ Yes | **~30–100 ms** | **high (for 13 labels)** | ✅ (fixed labels) | **★ Recommended (§6)** |
| Better off-the-shelf embedding + retrieval | ✅ Yes | ~50–200 ms | medium | ✅ | Weak — you already tested this (BGE/Qwen/Jina = 34–47 %) |
| Your current dictionary + anchor-cosine | ✅ Yes | ~90 ms | medium (plateaued) | ✅ | Works, but the ceiling you're hitting now |

Two things fall out of this table:

- For a **fast** kiosk, a model that does **one forward pass (a classifier)** beats one that **generates tokens (an LLM)** by 1–2 orders of magnitude in latency. "Use new AI" should mean *use an encoder classifier*, not *bolt on a chatbot*.
- The off-the-shelf embedding models you already benchmarked underperformed **because you used them in retrieval mode, untrained.** Fine-tuning a *smaller* encoder as a *classifier* on enough data is a different, much stronger setup.

---

## 6. ★ Recommended approach: the LLM-distilled small classifier

This is a well-established edge-AI pattern (**knowledge distillation → quantized student model**), and it's a near-perfect fit for your constraints. Four steps:

### Step 1 — Generate the data you never had (the key unlock)
Use a strong instruct LLM **at development time only** (this never ships) to synthesize a large, deliberately messy corpus of `(input → symptom labels)` pairs:
- All five language modes (Tagalog, Bisaya/Cebuano, English, Taglish/Conyo, Jejemon/leetspeak), plus heavy **code-switching**.
- The hard cases your dictionary can't hold: negation, contrastive ("pero/kaso"), idioms/figurative ("ubod ng init", "murag gibunalan"), run-ons, emotional rambling, severe misspellings, and **NONE / adversarial** inputs.
- Multi-symptom combinations sampled to *balance* the 13 labels (fixing the 8,192-combination sparsity).
- Target **10k–50k** examples. Then have your **Iteration-2 pharmacist** validate a *sample* (e.g. 300–500) — that sampled validation is your honest accuracy number and your answer to the panel's "who validated this?" question.

> This is the same idea as your current "288 LLM-generated cases," scaled up 50–100× and used for **training**, not just testing. It directly converts the panel's "synthetic benchmark" critique into a strength.

### Step 2 — Fine-tune a small multilingual encoder as a *classifier*
- **Student model:** a small multilingual encoder — e.g. `multilingual-e5-small` (~118 M) or even your existing `paraphrase-multilingual-MiniLM-L12-v2` (~33 M). Add a **multi-label sigmoid head** over 13 labels; train with BCE.
- This replaces *both* Stage 1's brittleness *and* Stage 2's weak anchor-cosine with **one** model that actually *generalizes* to phrasings it has never seen — which is the whole point your dictionary can't deliver.
- Because it's a **classifier**, the output space is locked to your 13 labels: it **cannot hallucinate** a symptom outside the set. That preserves your safety/auditability story.

### Step 3 — Quantize and make it Pi-fast
- Export to **ONNX Runtime** and apply **int8 dynamic quantization** (or `optimum` + `onnxruntime`). On a Pi-5 CPU, a quantized e5-small forward pass is roughly **30–100 ms**; MiniLM is faster. That is *faster* than your current ~93 ms hybrid and far more robust.
- Memory footprint: well under your 8 GB budget (a few hundred MB), fully offline.

### Step 4 — Keep the dictionary as a high-precision override, keep Stage 4 untouched
- Run the **dictionary first** as a fast, 100 %-precision shortcut for the obvious exact phrases (it's basically free and auditable). If it fires with high confidence, use it.
- Otherwise, use the **distilled classifier** instead of the anchor-cosine fallback.
- The **deterministic Stage-4 safety engine sits unchanged on top of whatever the NLU produces.** Symptoms are *suggestions*; safety rules are *law*. This is the same separation you already defend — you're only swapping the language-understanding box.

**Expected outcome:** higher accuracy on novel/idiomatic/code-switched input, the dictionary-maintenance treadmill mostly gone, latency the same or better, still 100 % offline, still safe, and a real answer to "your benchmark is self-authored" (you now have a large, pharmacist-sampled corpus).

---

## 7. Secondary option: a tiny constrained-decoding LLM (only if you need open-ended NLU)

If you later want the kiosk to handle truly open-ended descriptions (beyond 13 fixed labels), a **small** local LLM is now viable — but as a **fallback**, not the main path:

- **Models:** Qwen3-0.6B/1.7B, Llama-3.2-1B, Gemma-3-1B, or SmolLM2-1.7B (pick the current-best small multilingual model at build time), quantized to **Q4** via **llama.cpp / GGUF**.
- **Critical technique — constrained decoding:** force the output to a **JSON schema / GBNF grammar** (llama.cpp grammars, or Outlines) so the model can *only* emit valid symptom labels. This gives you LLM-level language flexibility while keeping output safe and parseable.
- **Reality check:** on a Pi-5 CPU these run at ~3–8 tok/s, so a short JSON output is ~**1–4 s** — too slow as the *primary* path for a snappy kiosk, fine as a *rare* fallback for inputs the classifier flags as low-confidence. Use it sparingly.

The encoder classifier (§6) is the better default; this is the "if you really need it" lever.

---

## 8. What NOT to do (anti-patterns for your setup)

- ❌ **Don't put a generative LLM on the recommendation/safety path.** Hallucinated drug names or missed negations are unacceptable. Your deterministic engine is the *correct* design — keep it.
- ❌ **Don't call a cloud API.** Breaks offline + RA 10173, the two pillars of your thesis.
- ❌ **Don't build RAG over 24 medicines.** RAG solves "too much knowledge to fit in context." You have a 24-row table. A dictionary lookup is strictly better here.
- ❌ **Don't chase the biggest model that "fits."** A 7B model that takes 30 s per query is worse than a 100 M classifier at 50 ms for *this* task. Smaller-and-trained beats bigger-and-generic in a narrow domain.
- ❌ **Don't replace the dictionary with the classifier entirely.** Keep it as a precision override — belt and suspenders.

---

## 9. Honest risks & how to validate

- **Distillation inherits the teacher's biases/errors.** The synthetic corpus is only as good as the prompt + the teacher model. → Mitigate with the pharmacist-validated sample (Step 1) and adversarial NONE cases.
- **You still need a held-out, externally-annotated test set** (your Iteration-2 pharmacist set). The distilled classifier doesn't remove that requirement — it makes it more important.
- **Calibration:** tune the sigmoid threshold per label on the validation set; keep your precision-first bias (favor missing a secondary symptom over a false positive).
- **Latency/memory budget:** measure the int8 model *on the actual Pi*, not the dev machine — your GTX-1070 dev box is irrelevant to deployment numbers.
- **Regression safety:** your existing 76-test regression suite + the 5-tier benchmark must still pass after the swap. Treat the classifier as a drop-in for Stage 1+2 and re-run everything.

---

## 10. Low-risk migration path (incremental — don't rip anything out)

1. **Keep the current system running.** Add the distilled classifier as a *parallel* Stage-2 candidate behind a flag.
2. **A/B on the pharmacist-annotated set:** dictionary-only vs. dictionary + classifier vs. current dictionary + anchor-cosine.
3. **Promote the classifier only if it beats the dictionary** on out-of-vocabulary recall *without* losing precision (your governing trade-off).
4. **Retire the anchor-cosine fallback** once the classifier wins; **keep the dictionary** as the high-precision override.
5. **Re-run the full 5-tier benchmark + regression suite** before shipping.

At no point do you touch the safety engine, the checkout/POS flow, or the offline guarantee.

---

## 11. How to frame this in the thesis (Iteration 2/3)

You can turn this into a strong "future work" section that *answers* the panel rather than retreating:

> *"Iteration 1 deliberately prioritized auditability and safety with a deterministic engine and a lexical-first NLU. Evaluation showed the semantic fallback under-contributes on in-distribution inputs; its value is out-of-vocabulary recall. For Iteration 2 we will replace the anchor-similarity fallback with a compact multilingual encoder classifier distilled from a large-language-model-generated, pharmacist-validated corpus — keeping all inference on-device and all safety decisions deterministic. This directly addresses the data-scarcity limitation observed in the transformer baselines (Table 10): the constraint was labeled data, not model capacity."*

That paragraph makes your Table-10 result a *setup* for your next step instead of a dead end.

---

## 12. Build-time shopping list (evaluate the current-best at implementation)

> AI moves fast; treat these as *categories*, and pick the strongest small option available when you build.

- **Student encoders (classifier):** `multilingual-e5-small`, `bge-small`, `gte-multilingual-base`, or your current MiniLM. Smallest that hits your accuracy bar.
- **Small local LLMs (optional fallback):** Qwen3-0.6B/1.7B, Llama-3.2-1B, Gemma-3-1B, SmolLM2-1.7B.
- **Edge inference / quantization:** ONNX Runtime, `optimum`, int8 dynamic quant; llama.cpp / GGUF (Q4) for any LLM path.
- **Constrained generation:** llama.cpp GBNF grammars, or `outlines` (JSON-schema-enforced decoding).
- **Data generation:** a strong instruct LLM (offline at dev time) + your pharmacist for sampled validation.
- **Training:** `sentence-transformers` / `transformers` + a small fine-tune; you don't need a big GPU for a 33–118 M student.

---

### Bottom line
Your instinct to be skeptical of the AI hype was *correct* — for the **safety** half of your system. The honest update is: **keep the deterministic safety core exactly as is, and modernize only the language-understanding front-end** by distilling a large LLM into a small, fast, offline classifier. That's the 2026-appropriate version of *your own* philosophy — small, fast, safe, on-device — done with the tools that now exist. You don't need a new architecture; you need a better Stage 2.
