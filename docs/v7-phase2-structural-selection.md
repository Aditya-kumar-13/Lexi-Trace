# V7 phase 2 structural selection

Status: frozen for calibration. This is development evidence, not final evaluation evidence.

## Selected configuration

| Component | Selected behavior | Reason |
|---|---|---|
| Semantic retrieval | Nearest stored example | Preserved both modes in the multimodal development cases; the centroid diluted distinct contexts. |
| Semantic retention | 12 examples per memory and polarity | Kept all storage and semantic-safety outcomes while reducing the stress payload by 33.4%. |
| Feedback scope | Automatic typed routing | Global rejection updates identity trust; contextual rejection updates context evidence. It restored lifecycle behavior without weakening semantic safety. |
| Conflict context floor | 0.20 | The 0.15 alternative made one wrong automatic edit. Both 0.20 and 0.25 prevented it, while 0.20 retained more coverage. |
| ASR reliability | Exact provider/model/route evidence | The broader model-level pool added no unique recovery. Removing learned reliability lost one known recovery. |
| Authorization | Boolean eligibility | Continuous posterior scoring reduced coverage and robustness without preventing an additional unsafe edit. |
| ASR confidence | Existing single feature with legacy contribution | A single-path alternative changed no final action and increased score clamping, so it did not satisfy the retention rule. |
| Phonetic matching | Metaphone in the product path | The Indic-aware prototype performed well on its isolated labeled set, but it has not earned promotion through identical pipeline inputs. |

These choices are now fixed while Phase 3 selects score transformations, weights, and thresholds.
The active v6 defaults remain unchanged until a versioned v7 policy passes calibration and every
safety gate.

## Combined development run

The combined candidate is reproducible with:

```powershell
.\.venv\Scripts\python.exe evaluation\run_v7_structural_candidate.py `
  --output results\v7\development\structural-candidate-v1
```

The run produced the following exact outcomes:

| Suite | Correct | Total | Wrong automatic edits |
|---|---:|---:|---:|
| Smoke | 28 | 28 | 0 |
| Robustness | 248 | 252 | 0 |
| Original journeys | 6 | 6 | 0 |
| Semantic multimodal | 6 | 6 | 0 |
| Semantic safety | 13 | 13 | 0 |
| Semantic storage | 8 | 8 | 0 |
| Learned ASR | 16 | 16 | 0 |
| Typed lifecycle | 16 | 16 | 0 |
| Conflicts | 5 | 5 | 0 |

The ASR ablation remained 15/16 and the lifecycle ablation remained 14/16, making both retained
behaviors reproducible rather than narrative claims.

## Re-instrumentation result

Across the 280 static cases, 242 candidates survived generation and deduplication. There were 242
unique `(memory_id, start, end)` keys and zero retained duplicates. The raw score mean was 0.997517,
the clamped mean was 0.967488, and 142/242 candidates exceeded the upper clamp before clamping.
This saturation is not hidden: it is the primary target of Phase 3 calibration.

Context control was `none` for 181 candidates, semantic for 48, sparse for 11, and tied for 2. The
manifest records candidate counts by retrieval route, the raw positive and negative sparse and
semantic distributions, every score-term contribution, suite hashes, latency/model usage, and
storage measurements. This closes the pre-calibration instrumentation gate without treating these
development cases as untouched evidence.

The external final holdout was not accessed. Its seal still awaits an independent custodian; that
blocks only the eventual final claim, not calibration or adversarial development.
