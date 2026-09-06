# LexiTrace chronological journey report

Dataset: `data/benchmark/v7_semantic_multimodal_development.jsonl`
SHA-256: `c19bf01d4002a502a6a7eef9afba9a96a8ab346acaa9220632afb388d2207ce9`
Local model: `BAAI/bge-small-en-v1.5`
Journeys: **2**

| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| sparse_ablation | 0.0% | 0.0% | 0 | 4.226 ms |
| hybrid | 100.0% | 100.0% | 0 | 93.300 ms |

## Operational accounting

### sparse_ablation

- Embedding execution: **disabled**
- Embedding calls: **0**
- Embedded input characters: **0**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **245760**
- Peak vector payload bytes: **0**

### hybrid

- Embedding execution: **local**
- Embedding calls: **12**
- Embedded input characters: **609**
- Hosted requests: **0**
- Estimated API cost: **$0.00**
- Peak allocated SQLite bytes: **278528**
- Peak vector payload bytes: **24294**


## Ablation differences

| Journey | Expected action | Sparse action |
|---|---|---|
| kivi-multimodal-contexts | apply | suggest |
| kivi-multimodal-contexts | apply | suggest |
| kivi-multimodal-contexts | apply | suggest |
| aaditya-multimodal-contexts | apply | suggest |
| aaditya-multimodal-contexts | apply | suggest |
| aaditya-multimodal-contexts | apply | suggest |

## Hybrid failures

No hybrid failures in this compact development suite.

## Interpretation

Events are executed in chronological order against an initially empty database. The hybrid system and sparse ablation receive identical teaching, correction, inference, and feedback events. This compact development suite demonstrates the mechanisms; it is not an external claim of production accuracy.
