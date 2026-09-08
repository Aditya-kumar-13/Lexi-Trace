# LexiTrace benchmark report

Dataset: `data/benchmark/v7_adversarial_round1.jsonl`
SHA-256: `6f1f66c925e2ea5132943734c0f46692e192c9d306a35b851cf2d8a0ec9e5dd6`
Cases: **40**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 60.0% | 0.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 40.0% | 40.0% | 40.0% | 100.0% | 60.0% | 0.000 ms |
| lexitrace | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 164.391 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **32**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **221184**
- Peak persisted trace payload bytes: **10421**

## Predeclared split results

| Split | Cases | Exact match | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| adversarial_discovery | 40 | 100.0% | 100.0% | 0 |

## LexiTrace failures

No failures in this benchmark.

## Interpretation

This is a bounded adversarial discovery suite, not a held-out or production-accuracy claim. Its complete case-level results remain visible for regression and review.
