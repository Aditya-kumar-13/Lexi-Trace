# LexiTrace chronological journey report

Dataset: `data/benchmark/v7_calibration_journeys.jsonl`
SHA-256: `69980c46e8bcf6aa061311d0c28a0b5e352bb68cafb3936c01a1308b5b4e9fc5`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **3**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 100.0% | 100.0% | 0 | 8.836 ms |
| hybrid | 100.0% | 100.0% | 0 | 148.038 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **241664**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **11**
- Embedded input characters: **402**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **249856**
- Peak vector payload bytes: **8090**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|

## Hybrid failures

No hybrid failures in this compact development suite.

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
