# Mendo Retrieval Model Dictionary

Date started: 2026-05-13

This document defines the benchmark models used for Mendo V3 symptom interpretation experiments. The goal is not to replace deterministic safety rules. The goal is to measure whether newer retrieval models improve multilingual OTC symptom matching while keeping recommendations deterministic and explainable.

## Evaluation Boundary

All models in this benchmark are restricted to approved symptom labels from the Mendo corpus. They do not generate diagnoses, medicines, or free-form medical advice.

The deterministic recommendation engine still checks:

- red flags
- age and duration constraints
- condition warnings
- contraindications
- medicine availability
- recommendation safety

## Local Environment

Observed benchmark environment:

- CPU path used by default
- system Python packages:
  - `torch 2.10.0+cu128`
  - `transformers 5.0.0`
  - `sentence-transformers 5.2.2`
- Jina benchmark virtualenv:
  - `transformers 4.57.3`
  - `einops 0.8.2`
- GPU detected: NVIDIA GeForce GTX 1070 Max-Q
- GPU caveat: installed PyTorch does not support this GPU's CUDA compute capability, so model timings are CPU timings

This matters for deployment because Raspberry Pi inference is also CPU-first unless an external accelerator or server is used.

## Model Registry

| Model ID | Type | Purpose | Production Risk |
| --- | --- | --- | --- |
| `dictionary` | deterministic rules | Safety-first lexical baseline | Low |
| `current_hybrid` | dictionary + MiniLM fallback | Current Mendo NLP system | Low to medium |
| `tfidf_word` | classical retrieval | Fast lexical baseline | Medium, weak recall |
| `tfidf_char` | classical retrieval | Typo-tolerant lexical baseline | Medium, weak semantics |
| `tfidf_hybrid` | classical retrieval | Combines word and character TF-IDF | Medium |
| `minilm` | embedding retrieval | Current lightweight multilingual semantic baseline | Medium |
| `qwen3_embedding_0_6b` | embedding retrieval | Modern multilingual embedding experiment | High latency on CPU |
| `bge_m3` | embedding retrieval | Modern multilingual embedding experiment | Medium to high latency |
| `jina_v3` | embedding retrieval | Modern multilingual embedding experiment | Compatibility and license concerns |
| `minilm_qwen3_rerank` | retrieval + reranker | Hybrid reranking experiment | High latency on CPU |

## Deterministic Dictionary

Source:

- current Mendo `mendo_core.step1` symptom dictionary
- current Mendo `mendo_core.step3_hybrid` red-flag and hybrid report path

Strengths:

- fastest among high-accuracy systems
- most explainable
- easiest to defend during thesis panel review
- safest for known Filipino/Bisaya phrases already encoded

Weaknesses:

- depends on manually curated phrases
- can miss unseen phrasing
- requires continuous vocabulary maintenance

Recommended role:

- mandatory first layer
- mandatory fallback layer
- do not remove

## Current Hybrid

Source:

- deterministic dictionary
- current MiniLM semantic fallback

Strengths:

- preserves deterministic first pass
- supports semantic fallback when dictionary misses
- safer than unrestricted generative models

Weaknesses:

- semantic fallback can introduce false positives
- latency is higher than dictionary-only
- does not outperform dictionary on the current benchmark set

Recommended role:

- local Pi-compatible baseline
- keep as a benchmark reference
- tune fallback thresholds before production changes

## TF-IDF Models

Variants:

- `tfidf_word`
- `tfidf_char`
- `tfidf_hybrid`

Strengths:

- very fast
- lightweight
- reproducible
- good thesis baseline because it represents a classical retrieval method

Weaknesses:

- poor semantic understanding
- weak on code-switching and paraphrase
- top-k thresholding easily over-predicts

Recommended role:

- baseline only
- not preferred for final production recommendation logic

## Qwen3 Embedding 0.6B

Model:

- `Qwen/Qwen3-Embedding-0.6B`

Benchmark adapter:

- SentenceTransformers
- CPU device
- top-1 retrieval for the full clarified benchmark
- native `query` prompt for the fairer run

Strengths:

- modern multilingual embedding architecture
- improved when using model-native query prompt
- no red-flag OTC leakage in benchmark because safety remains deterministic

Weaknesses observed:

- much slower than dictionary, TF-IDF, current hybrid, and BGE-M3 on this machine
- did not outperform current Mendo rules on the existing corpus
- generic web-search query prompt may not match OTC symptom-intent retrieval perfectly

Recommended role:

- server-side or offline research candidate
- not Pi-local default without quantization and stronger benchmark results

## BGE-M3

Model:

- `BAAI/bge-m3`

Benchmark adapter:

- SentenceTransformers
- CPU device
- top-1 retrieval

Strengths:

- best modern embedding model in the current full clarified run
- substantially faster than Qwen3 and Jina in this environment
- good candidate for server-side or stronger Pi-class hardware testing

Weaknesses observed:

- still far below deterministic/current hybrid accuracy on the current dataset
- needs a richer candidate corpus and threshold tuning before judging final quality

Recommended role:

- strongest modern embedding candidate so far
- use for the next retrieval-corpus improvement experiment
- good model to pair with a reranker in a server-side experiment

## Jina Embeddings v3

Model:

- `jinaai/jina-embeddings-v3`

Benchmark adapter:

- SentenceTransformers
- benchmark-only virtualenv required
- CPU device
- two runs tracked:
  - unprompted/prefix-style run
  - native `retrieval.query` and `retrieval.passage` prompt run

Strengths:

- multilingual model family
- supports task-specific prompts

Weaknesses observed:

- required extra environment fixes
- needed `einops`
- needed `transformers 4.57.3` in the benchmark virtualenv because system `transformers 5.0.0` failed
- no FlashAttention available, so CPU latency was high
- native retrieval prompts performed worse on the current symptom-candidate corpus
- model card license is `cc-by-nc-4.0`, which is important for deployment planning

Recommended role:

- research-only unless licensing and environment compatibility are resolved
- not preferred for Raspberry Pi local deployment

## Reranker Experiments

Planned model:

- `Qwen/Qwen3-Reranker-0.6B`

Expected role:

- rerank only top-k retrieved candidates
- never invent labels
- never override red flags or safety rules

Current status:

- adapter is scaffolded as `minilm_qwen3_rerank`
- full benchmark has not been completed because CPU latency is expected to be high

Recommended role:

- server-side experiment first
- Pi-local only if quantized and top-k is very small

## Sources

- Qwen3 Embedding model card: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 model card: https://huggingface.co/jinaai/jina-embeddings-v3
- Current MiniLM baseline: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
