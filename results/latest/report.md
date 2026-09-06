# LexiTrace benchmark report

Dataset: `data/benchmark/smoke.jsonl`  
SHA-256: `592a8b46327b6e06f8294cb741f862e4f775bc846172331ed7d421c43e911b59`  
Cases: **28**

## System comparison

| System | Exact match | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|
| no_memory | 57.1% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 67.9% | 60.0% | 75.0% | 21.4% | 0.000 ms |
| lexitrace | 100.0% | 100.0% | 100.0% | 0.0% | 4.490 ms |

## LexiTrace failures

No failures in this smoke benchmark.

## Interpretation

This is the initial north-star smoke suite, not the final claimed benchmark. Its purpose is to keep positive corrections, contextual negatives, candidate memories, conflicts, boundaries, and lifecycle behavior executable while the larger curated benchmark is built.
