# LexiTrace benchmark report

Dataset: `data/benchmark/smoke.jsonl`
SHA-256: `3455df3d22b8ed106f0eee83ecd45221310c7450988073808b9a39993a5d55f8`
Cases: **28**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 57.1% | 25.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 67.9% | 53.6% | 60.0% | 75.0% | 21.4% | 0.000 ms |
| lexitrace | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 117.047 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **16**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **176128**
- Peak persisted trace payload bytes: **4155**

## LexiTrace failures

No failures in this smoke benchmark.

## Interpretation

This is the north-star smoke suite, not a production-accuracy claim. Contextual cases are initialized from observed correction sentences rather than source-code keyword gates.
