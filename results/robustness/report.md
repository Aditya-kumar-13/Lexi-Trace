# LexiTrace benchmark report

Dataset: `data/benchmark/robustness.jsonl`
SHA-256: `70f53d755220ef7b6244f375ff0978a2b620347fed69cb64b7048dabc624458e`
Cases: **252**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 53.2% | 23.0% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 53.2% | 53.2% | 50.0% | 74.6% | 34.9% | 0.000 ms |
| lexitrace | 98.4% | 98.4% | 100.0% | 96.6% | 0.0% | 179.480 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **192**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **212992**
- Peak persisted trace payload bytes: **5403**

## Predeclared split results

| Split | Cases | Exact match | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| calibration | 109 | 97.2% | 97.2% | 0 |
| heldout | 143 | 99.3% | 99.3% | 0 |

## LexiTrace failures

| Case | Category | Expected | Actual | Action |
|---|---|---|---|---|
| global-unseen-phonetic-01-00 | global-unseen-phonetic-positive | Message Aaditya before lunch. | Message Adithya before lunch. | suggest |
| global-unseen-phonetic-01-01 | global-unseen-phonetic-positive | Ask Aaditya to open the file. | Ask Adithya to open the file. | suggest |
| global-unseen-phonetic-01-02 | global-unseen-phonetic-positive | The Aaditya item is ready. | The Adithya item is ready. | suggest |
| context-positive-01-02 | contextual-positive | Inspect the Postgres query logs. | Inspect the post grass query logs. | suggest |

## Interpretation

This is a fixed synthetic robustness suite with a predeclared calibration/held-out split. It exercises the complete hybrid product and keeps all failures visible; it is not an external or production-accuracy claim.
