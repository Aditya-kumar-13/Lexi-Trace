# LexiTrace chronological journey report

Dataset: `data/benchmark/v7_semantic_safety_development.jsonl`
SHA-256: `c4a02d40e27a47cf7ce4518a702e78cae5bdfe04050690673f9ac5818dba8157`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **2**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 53.8% | 23.1% | 0 | 5.961 ms |
| hybrid | 100.0% | 100.0% | 0 | 98.070 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **307200**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **28**
- Embedded input characters: **1674**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **376832**
- Peak vector payload bytes: **48435**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| kivi-negative-feedback-neighborhood | suggest | apply |
| kivi-negative-feedback-neighborhood | suggest | apply |
| kivi-negative-feedback-neighborhood | abstain | suggest |
| kivi-negative-feedback-neighborhood | abstain | suggest |
| kivi-negative-feedback-neighborhood | abstain | suggest |
| kivi-negative-feedback-neighborhood | abstain | suggest |
| kivi-negative-feedback-neighborhood | apply | suggest |
| kivi-negative-feedback-neighborhood | apply | suggest |
| kivi-negative-feedback-neighborhood | apply | suggest |
| kiwi-overlapping-memory-collision | apply | suggest |
| kiwi-overlapping-memory-collision | apply | suggest |
| kiwi-overlapping-memory-collision | apply | suggest |

## Hybrid failures

| Journey | Expected output | Actual output | Expected action | Actual action |
|---|---|---|---|---|
| kivi-negative-feedback-neighborhood | The grocery launch positions kiwi as our seasonal fruit promotion. | The grocery launch positions Kivi as our seasonal fruit promotion. | suggest | apply |
| kivi-negative-feedback-neighborhood | Legal approved the kiwi import label for the produce shipment. | Legal approved the Kivi import label for the produce shipment. | suggest | apply |

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
