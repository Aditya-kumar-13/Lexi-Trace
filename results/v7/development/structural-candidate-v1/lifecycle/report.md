# Memory lifecycle journey report

Dataset: `data/benchmark/lifecycle_journeys.jsonl`  
SHA-256: `bf48c310ae6711b88c5bc2f5ebe26f857ddb1e95c2ba878f97663f2bdca5fcf1`  
Journeys: **5**

| System | Event accuracy | Failed events | Wrong interventions |
|---|---:|---:|---:|
| no_lifecycle_ablation | 87.5% | 2 | 0 |
| event_lifecycle | 100.0% | 0 | 0 |

The ablation receives and stores the same observations, but automatic promotion and demotion are disabled. Explicit teaching and suppression remain user-authorized in both systems. Every assertion and posterior component is retained in `cases.json`.
