# LexiTrace chronological journey report

Dataset: `data/benchmark/v7_semantic_storage_development.jsonl`
SHA-256: `4801f914d258d6b80f0ec5a23725618e1a4c1bbf89accc28bf9b98af717e6654`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **1**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 12.5% | 12.5% | 0 | 10.711 ms |
| hybrid | 100.0% | 100.0% | 0 | 182.846 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **438272**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **25**
- Embedded input characters: **1450**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **573440**
- Peak vector payload bytes: **96904**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |
| bounded-diverse-semantic-memory | apply | suggest |

## Hybrid failures

No hybrid failures in this compact development suite.

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
