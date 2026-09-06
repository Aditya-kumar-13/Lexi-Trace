# Learned ASR reliability journey report

Dataset: `data/benchmark/asr_journeys.jsonl`  
SHA-256: `3e11769754ecec1508f0fe4418a8f19e7f4023b5967924db48dc7c55de683a1f`  
Journeys: **4**

| System | Exact output | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| no_learning_ablation | 93.8% | 93.8% | 0 | 4.851 ms |
| learned_asr | 100.0% | 100.0% | 0 | 5.368 ms |

## Precision and coverage

The curve replays the committed chronological labels at alternate apply thresholds. Training suggestions explicitly confirmed by the user count as useful candidates.

| Threshold | Interventions | Precision | Useful-candidate coverage |
|---:|---:|---:|---:|
| 0.90 | 15 | 86.7% | 100.0% |
| 0.92 | 1 | 100.0% | 7.7% |
| 0.93 | 1 | 100.0% | 7.7% |
| 0.94 | 1 | 100.0% | 7.7% |
| 0.96 | 0 | 100.0% | 0.0% |

## Interpretation

The product and ablation receive the same events. Only the learned ASR contribution is disabled in the ablation. Provider, model, rank, and exact confusion pair are part of the reliability key, and context blockers remain authoritative. This synthetic suite demonstrates mechanism and regression safety; it is not a production accuracy claim.
