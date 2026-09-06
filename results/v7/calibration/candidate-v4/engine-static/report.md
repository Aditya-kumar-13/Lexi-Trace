# LexiTrace benchmark report

Dataset: `data/benchmark/v7_calibration.jsonl`
SHA-256: `bd3ce16a3f591a277b99bb193564f403427209e34d37c5dd8c47d249f5e0adc9`
Cases: **62**

## System comparison

| System | Exact match | Action accuracy | Precision | Recall | Incorrect interventions | p95 latency |
|---|---:|---:|---:|---:|---:|---:|
| no_memory | 32.3% | 9.7% | n/a | 0.0% | 0.0% | 0.000 ms |
| naive_dictionary | 74.2% | 74.2% | 74.1% | 95.2% | 22.6% | 0.000 ms |
| lexitrace | 98.4% | 95.2% | 100.0% | 97.6% | 0.0% | 164.206 ms |

## Operational accounting

- Embedding execution: **local**
- Embedding calls: **46**
- Hosted model requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **221184**
- Peak persisted trace payload bytes: **10449**

## Predeclared split results

| Split | Cases | Exact match | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| calibration | 62 | 98.4% | 95.2% | 0 |

## LexiTrace failures

| Case | Category | Expected | Actual | Action |
|---|---|---|---|---|
| cal-context-positive-02-02 | contextual-positive | Review Aiven service alerts before the migration. | Review Ivan service alerts before the migration. | suggest |
| cal-asr-alternative-02 | asr-alternative-confidence | Open the monitoring overview. | Open the monitoring overview. | suggest |
| cal-asr-alternative-03 | asr-alternative-confidence | Open the monitoring overview. | Open the monitoring overview. | suggest |

## Interpretation

This is a fixed synthetic robustness suite with a predeclared calibration/held-out split. It exercises the complete hybrid product and keeps all failures visible; it is not an external or production-accuracy claim.
