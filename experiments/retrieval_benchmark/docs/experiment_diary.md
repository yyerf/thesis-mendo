# Mendo Retrieval Experiment Diary

Date: 2026-05-13

This diary records benchmark runs for Mendo V3 multilingual OTC symptom interpretation. The production kiosk code was not changed. All experiments are isolated under `experiments/retrieval_benchmark`.

## Research Question

Can modern retrieval models improve Mendo V3 symptom interpretation compared with the current deterministic and MiniLM-based pipeline while preserving deterministic safety?

## Safety Rule

Every benchmarked model can only return approved symptom labels. Red-flag handling and OTC recommendation decisions remain deterministic. A model is not acceptable if it causes red-flag OTC recommendation leakage.

## Dataset

Dataset:

```text
testing/benchmark/testing.csv
```

Loaded examples:

```text
288
```

Important caveat:

The current CSV does not include a filled `language` column, so per-language reporting currently groups all rows as `unspecified`. The category names still include useful subsets such as Bisaya-heavy, code-switching, misspelling, negation, and triage cases.

## Benchmark Modes

Raw NLP mode:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models dictionary,current_hybrid,tfidf_word,tfidf_char,tfidf_hybrid \
  --dataset testing/benchmark/testing.csv
```

Clarified kiosk-flow mode:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models dictionary,current_hybrid,tfidf_word,tfidf_char,tfidf_hybrid \
  --dataset testing/benchmark/testing.csv \
  --apply-clarification
```

Clarified mode is closer to actual kiosk behavior because cough dry/productive labels require a deterministic clarification answer.

## Baseline Results

Run:

```text
experiments/retrieval_benchmark/results/run_20260513_220845/
```

Mode:

```text
clarified kiosk-flow
```

| Model | Accuracy | Micro F1 | Macro F1 | p95 ms | Safety leaks |
| --- | ---: | ---: | ---: | ---: | ---: |
| `dictionary` | 99.31% | 0.9972 | 0.9951 | 6.684 | 0 |
| `current_hybrid` | 98.26% | 0.9930 | 0.9918 | 23.979 | 0 |
| `tfidf_word` | 46.88% | 0.6742 | 0.6328 | 1.351 | 0 |
| `tfidf_char` | 53.47% | 0.7516 | 0.7358 | 1.408 | 0 |
| `tfidf_hybrid` | 53.12% | 0.7513 | 0.7355 | 1.902 | 0 |

Interpretation:

The deterministic dictionary is currently the best overall performer on the curated benchmark. The current hybrid system is close but slightly worse and slower. TF-IDF is fast but not accurate enough for production symptom interpretation.

## Modern Embedding Smoke Tests

Initial smoke tests used only the first 5 rows.

Observation:

For the repeated text `umuubo ako`, embeddings often predicted `COUGH_GENERAL`. This is reasonable because dry/productive distinction is not present in the text itself. In the deployed kiosk, that distinction should come from the deterministic clarification layer.

## Full Modern Embedding Run: BGE-M3 and Qwen3

Command:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models qwen3_embedding_0_6b,bge_m3 \
  --dataset testing/benchmark/testing.csv \
  --apply-clarification \
  --top-k 1 \
  --threshold 0.0
```

Run:

```text
experiments/retrieval_benchmark/results/run_20260513_223556/
```

| Model | Prompt mode | Accuracy | Micro F1 | Macro F1 | p95 ms | Safety leaks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3_embedding_0_6b` | manual query prefix | 37.15% | 0.5719 | 0.5124 | 827.840 | 0 |
| `bge_m3` | default | 46.53% | 0.7088 | 0.6309 | 165.946 | 0 |

Interpretation:

BGE-M3 is the strongest modern embedding candidate in this run. Qwen3 was slower and less accurate with the first manual prompt strategy.

## Qwen3 Native Prompt Run

Change:

The adapter was updated to use Qwen's native SentenceTransformers `query` prompt instead of a manual prefix.

Command:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models qwen3_embedding_0_6b \
  --dataset testing/benchmark/testing.csv \
  --apply-clarification \
  --top-k 1 \
  --threshold 0.0
```

Run:

```text
experiments/retrieval_benchmark/results/run_20260513_225022/
```

| Model | Prompt mode | Accuracy | Micro F1 | Macro F1 | p95 ms | Safety leaks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `qwen3_embedding_0_6b` | native `query` prompt | 42.36% | 0.6547 | 0.6181 | 1109.934 | 0 |

Interpretation:

Using the native Qwen prompt improved accuracy and F1, but latency became very high. It still did not outperform BGE-M3, current hybrid, or deterministic dictionary on this benchmark.

## Jina Embeddings v3 Runs

Jina required benchmark-only environment work:

```bash
python3 -m venv --system-site-packages experiments/retrieval_benchmark/.venv
experiments/retrieval_benchmark/.venv/bin/python -m pip install einops
experiments/retrieval_benchmark/.venv/bin/python -m pip install 'transformers==4.57.3'
```

Reason:

The system Python had `transformers 5.0.0`, and the Jina remote model loader failed in that environment. The benchmark virtualenv keeps this compatibility workaround outside the production app.

### Jina Unprompted/Prefix-Style Run

Run:

```text
experiments/retrieval_benchmark/results/run_20260513_224258/
```

| Model | Prompt mode | Accuracy | Micro F1 | Macro F1 | p95 ms | Safety leaks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `jina_v3` | earlier prefix-style adapter | 34.03% | 0.5889 | 0.5674 | 564.558 | 0 |

### Jina Native Retrieval Prompt Run

Change:

The adapter was updated to use Jina's native `retrieval.query` and `retrieval.passage` prompts.

Run:

```text
experiments/retrieval_benchmark/results/run_20260513_225745/
```

| Model | Prompt mode | Accuracy | Micro F1 | Macro F1 | p95 ms | Safety leaks |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `jina_v3` | native retrieval prompts | 19.10% | 0.4266 | 0.3855 | 659.541 | 0 |

Interpretation:

Native Jina retrieval prompts performed worse for the current Mendo symptom-candidate corpus. This does not prove Jina is a weak model generally; it suggests the current candidate documents are not shaped like Jina's expected evidence-passage retrieval task.

## Best Result So Far

For current Mendo benchmark data:

| Rank | Model | Accuracy | Micro F1 | p95 ms | Deployment note |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | `dictionary` | 99.31% | 0.9972 | 6.684 | Best current local production choice |
| 2 | `current_hybrid` | 98.26% | 0.9930 | 23.979 | Good current system baseline |
| 3 | `tfidf_char` | 53.47% | 0.7516 | 1.408 | Fast but too inaccurate |
| 4 | `bge_m3` | 46.53% | 0.7088 | 165.946 | Best modern embedding so far |
| 5 | `qwen3_embedding_0_6b` native prompt | 42.36% | 0.6547 | 1109.934 | Too slow locally |
| 6 | `jina_v3` unprompted/prefix-style | 34.03% | 0.5889 | 564.558 | Environment and license concerns |

Conclusion:

The modern models did not beat the existing deterministic/current hybrid system on the current dataset. The strongest modern candidate so far is BGE-M3, but it needs a better candidate corpus and possibly a reranker before it is production-worthy.

## Thesis Interpretation

The panel is correct that newer retrieval technologies should be tested. The benchmark now shows that simply swapping in a modern embedding model is not automatically better.

The likely reason:

The current benchmark and candidate corpus are highly aligned with the deterministic dictionary. Modern embedding models need richer symptom-intent documents, contrastive negative examples, and possibly a reranker to show their value on unseen phrasing.

This is thesis-useful because the project can defend a safety-first architecture:

- deterministic rules are empirically strongest for known high-risk OTC flows
- modern semantic retrieval can be evaluated as an auxiliary layer
- BGE-M3 is the most promising modern candidate so far
- no model is allowed to override deterministic safety

## Next Experiments

1. Add a `language` column to `testing/benchmark/testing.csv`.
2. Expand candidate documents from phrase lists into short multilingual symptom-intent descriptions.
3. Add contrastive negatives such as `not fever`, `no cough`, `blood in stool`, and diagnostic-condition mentions.
4. Evaluate BGE-M3 again after corpus expansion.
5. Test reranking with `Qwen/Qwen3-Reranker-0.6B` on top-5 BGE candidates.
6. Add threshold sweeps for top-1, top-2, and top-3 retrieval.
7. Run a Raspberry Pi benchmark separately because this laptop CPU test is not equivalent to Pi 5 latency.

## Source Links

- Qwen3 Embedding model card: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 model card: https://huggingface.co/jinaai/jina-embeddings-v3
- MiniLM baseline model card: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
