# V7 phase 3 calibration result

Status: calibration and regression complete. Candidate 4 is the active v7 policy.

## Selected policy

Candidate 4 searched 25,920 combinations after the frozen architecture required a nonzero phonetic
contribution and calibration required 0.0025 of headroom around the apply boundary. The selected
constants are:

```toml
apply = 0.90
suggest = 0.72
lexical = 0.65
memory_authorization = 0.14
context = 0.15
phonetic = 0.05
asr_alternative = 0.05
learned_asr = 0.21
negative_context = 0.65
context_transform = "legacy_power_035"
```

The replayed v6 formula exactly matched the engine baseline: 65/72 exact, 64/72 correct actions,
and five wrong automatic edits. Candidate 4 reached 71/72 exact outputs, 69/72 correct actions,
zero wrong automatic edits, zero scores within the declared apply-boundary band, and zero upper or
lower clamps across 74 candidates. Its independent post-selection safety result was 16/16 with no
wrong automatic edit.

Exact engine execution reproduced the selected result: 61/62 static cases plus 10/10 lifecycle
events, again with zero wrong automatic edits. One contextual case remains a safe suggestion because
its semantic evidence does not clear the eligibility gate. Two lower-confidence ASR cases suggest
rather than abstain; neither edits the text.

## Frozen regression result

| Suite | Correct | Total | Wrong automatic edits |
|---|---:|---:|---:|
| Smoke | 27 | 28 | 0 |
| Robustness | 239 | 252 | 0 |
| Original journeys | 6 | 6 | 0 |
| Semantic multimodal | 6 | 6 | 0 |
| Semantic safety | 11 | 13 | 0 |
| Semantic storage | 8 | 8 | 0 |
| Learned ASR | 16 | 16 | 0 |
| Typed lifecycle | 16 | 16 | 0 |
| Conflicts | 5 | 5 | 0 |

The coverage regression is explicit: v6 produced 248/252 on the robustness corpus, while calibrated
v7 produces 239/252. The additional misses are abstentions or suggestions, not wrong edits. This is
accepted for this safety-first policy because the calibration corpus removed five demonstrated wrong
automatic edits and the fixed zero-wrong gate holds everywhere. Future coverage work must occur in a
new calibrated policy version rather than weakening v7 after seeing regression results.

Candidate 1 was rejected for an unidentifiable tie, Candidate 2 for eliminating the retained
phonetic contribution, and Candidate 3 for landing on a quantized decision boundary. Their complete
search results and failure evidence remain committed.

The final holdout was not accessed. Phase 4 is the bounded two-round adversarial workflow.
