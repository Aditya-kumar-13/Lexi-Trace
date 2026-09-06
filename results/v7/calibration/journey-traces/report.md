# LexiTrace chronological journey report

Dataset: `data/benchmark/v7_calibration_journeys.jsonl`
SHA-256: `69980c46e8bcf6aa061311d0c28a0b5e352bb68cafb3936c01a1308b5b4e9fc5`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **3**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 50.0% | 50.0% | 4 | 10.100 ms |
| hybrid | 50.0% | 50.0% | 4 | 102.462 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **253952**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **11**
- Embedded input characters: **402**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **262144**
- Peak vector payload bytes: **8095**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| cal-learn-exact-asr-route | apply | suggest |
| cal-asr-route-does-not-cross-model | suggest | apply |
| cal-asr-route-does-not-cross-model | suggest | apply |
| cal-asr-route-does-not-cross-model | suggest | apply |
| cal-asr-route-does-not-cross-model | suggest | apply |

## Hybrid failures

| Journey | Expected output | Actual output | Expected action | Actual action |
|---|---|---|---|---|
| cal-learn-exact-asr-route | Ask Nivetha to inspect the release. | Ask Nivitha to inspect the release. | apply | suggest |
| cal-asr-route-does-not-cross-model | Message Dhruvie about the review. | Message Dhruvi about the review. | suggest | apply |
| cal-asr-route-does-not-cross-model | Message Dhruvie about the review. | Message Dhruvi about the review. | suggest | apply |
| cal-asr-route-does-not-cross-model | Message Dhruvie about the review. | Message Dhruvi about the review. | suggest | apply |
| cal-asr-route-does-not-cross-model | Message Dhruvie about the review. | Message Dhruvi about the review. | suggest | apply |

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
