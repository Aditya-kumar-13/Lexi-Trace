# LexiTrace chronological journey report

Dataset: `data/benchmark/journeys.jsonl`
SHA-256: `7a7b95fc6e74dd062156b4e9041e5117b6df14b5b527553b0a1f3ccbe9548819`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **3**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 83.3% | 66.7% | 0 | 12.047 ms |
| hybrid | 100.0% | 100.0% | 0 | 90.008 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **229376**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **7**
- Embedded input characters: **261**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **241664**
- Peak vector payload bytes: **16142**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| semantic-generalization | apply | suggest |
| negative-prototype-recovery | abstain | suggest |

## Hybrid failures

No hybrid failures in this compact development suite.

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
