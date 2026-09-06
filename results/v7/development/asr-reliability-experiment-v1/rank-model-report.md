# Learned ASR reliability journey report

Dataset: `data/benchmark/v7_asr_route_development.jsonl`  
SHA-256: `bc14b20d67eb1eebed14e7a49b3ff48b56210de1ff7b69ead6bb06199cdf5f35`  
Journeys: **2**

| System | Exact output | Action accuracy | Wrong interventions | p95 latency |
|---|---:|---:|---:|---:|
| no_learning_ablation | 50.0% | 50.0% | 0 | 4.055 ms |
| learned_asr | 50.0% | 50.0% | 0 | 4.314 ms |

## Precision and coverage

The curve replays the committed chronological labels at alternate apply thresholds. Training suggestions explicitly confirmed by the user count as useful candidates.

| Threshold | Interventions | Precision | Useful-candidate coverage |
|---:|---:|---:|---:|
| 0.90 | 0 | 100.0% | 0.0% |
| 0.92 | 0 | 100.0% | 0.0% |
| 0.93 | 0 | 100.0% | 0.0% |
| 0.94 | 0 | 100.0% | 0.0% |
| 0.96 | 0 | 100.0% | 0.0% |

## Interpretation

The product and ablation receive the same events. Only the learned ASR contribution is disabled in the ablation. Provider, model, rank, and exact confusion pair are part of the reliability key, and context blockers remain authoritative. This synthetic suite demonstrates mechanism and regression safety; it is not a production accuracy claim.
