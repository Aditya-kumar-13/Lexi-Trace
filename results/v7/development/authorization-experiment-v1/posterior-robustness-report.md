# LexiTrace benchmark report

Dataset: `data/benchmark/robustness.jsonl`
SHA-256: `70f53d755220ef7b6244f375ff0978a2b620347fed69cb64b7048dabc624458e`
Cases: **252**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 53.2% | 23.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 53.2% | 53.2% | 50.0% | 74.6% | 34.9% | 0.000 ms |
| lexitrace | 94.8% | 94.8% | 100.0% | 89.0% | 0.0% | 109.904 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **192**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **221184**
- Peak persisted trace payload bytes: **10649**

## Predeclared split results

| Split | Cases | Exact match | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| calibration | 109 | 90.8% | 90.8% | 0 |
| heldout | 143 | 97.9% | 97.9% | 0 |

## LexiTrace failures

| Case | Category | Expected | Actual | Action |
|---|---|---|---|---|
| global-unseen-phonetic-01-00 | global-unseen-phonetic-positive | Message Aaditya before lunch. | Message Adithya before lunch. | suggest |
| global-unseen-phonetic-01-01 | global-unseen-phonetic-positive | Ask Aaditya to open the file. | Ask Adithya to open the file. | suggest |
| global-unseen-phonetic-01-02 | global-unseen-phonetic-positive | The Aaditya item is ready. | The Adithya item is ready. | suggest |
| global-unseen-phonetic-02-00 | global-unseen-phonetic-positive | Message Sarvam before lunch. | Message Sarvum before lunch. | suggest |
| global-unseen-phonetic-02-01 | global-unseen-phonetic-positive | Ask Sarvam to open the file. | Ask Sarvum to open the file. | suggest |
| global-unseen-phonetic-02-02 | global-unseen-phonetic-positive | The Sarvam item is ready. | The Sarvum item is ready. | suggest |
| global-unseen-phonetic-06-00 | global-unseen-phonetic-positive | Message Qdrant before lunch. | Message Qdrent before lunch. | suggest |
| global-unseen-phonetic-06-01 | global-unseen-phonetic-positive | Ask Qdrant to open the file. | Ask Qdrent to open the file. | suggest |
| global-unseen-phonetic-06-02 | global-unseen-phonetic-positive | The Qdrant item is ready. | The Qdrent item is ready. | suggest |
| global-unseen-phonetic-07-00 | global-unseen-phonetic-positive | Message Shivangi before lunch. | Message Shivangee before lunch. | suggest |
| global-unseen-phonetic-07-01 | global-unseen-phonetic-positive | Ask Shivangi to open the file. | Ask Shivangee to open the file. | suggest |
| global-unseen-phonetic-07-02 | global-unseen-phonetic-positive | The Shivangi item is ready. | The Shivangee item is ready. | suggest |
| context-positive-01-02 | contextual-positive | Inspect the Postgres query logs. | Inspect the post grass query logs. | suggest |

## Interpretation

This is a fixed synthetic robustness suite with a predeclared calibration/held-out split. It exercises the complete hybrid product and keeps all failures visible; it is not an external or production-accuracy claim.
