# LexiTrace chronological journey report

Dataset: `data/benchmark/journeys.jsonl`
SHA-256: `7a7b95fc6e74dd062156b4e9041e5117b6df14b5b527553b0a1f3ccbe9548819`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **3**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 83.3% | 66.7% | 0 | 9.950 ms |
| hybrid | 100.0% | 100.0% | 0 | 174.528 ms |

## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| semantic-generalization | apply | suggest |
| negative-prototype-recovery | abstain | suggest |

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
