# LexiTrace benchmark report

Dataset: `data/benchmark/v7_calibration_safety.jsonl`
SHA-256: `8ec6a847853d197ba29f4f328cb73516147c51181c567574d0e3be8bd86c726a`
Cases: **16**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 75.0% | 0.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 50.0% | 25.0% | 33.3% | 100.0% | 50.0% | 0.000 ms |
| lexitrace | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 106.933 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **24**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **221184**
- Peak persisted trace payload bytes: **6243**

## Predeclared split results

| Split | Cases | Exact match | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| calibration | 16 | 100.0% | 100.0% | 0 |

## LexiTrace failures

No failures in this smoke benchmark.

## Interpretation

This is a fixed synthetic robustness suite with a predeclared calibration/held-out split. It exercises the complete hybrid product and keeps all failures visible; it is not an external or production-accuracy claim.
