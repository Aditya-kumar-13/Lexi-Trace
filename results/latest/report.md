# LexiTrace benchmark report

Dataset: `data/benchmark/smoke.jsonl`
SHA-256: `3455df3d22b8ed106f0eee83ecd45221310c7450988073808b9a39993a5d55f8`
Cases: **28**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 57.1% | 25.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 67.9% | 53.6% | 60.0% | 75.0% | 21.4% | 0.000 ms |
| lexitrace | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 5.982 ms |

## LexiTrace failures

No failures in this smoke benchmark.

## Interpretation

This is the initial north-star smoke suite, not the final claimed benchmark. Contextual cases are initialized from observed correction sentences rather than hand-written keyword gates. The suite keeps learned context, candidate memories, conflicts, boundaries, and lifecycle behavior executable while the larger curated journey benchmark is built.
