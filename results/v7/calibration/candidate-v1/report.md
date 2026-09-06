# V7 score calibration candidate 1

Search candidates: **23328**
Calibration cases: **72**
Safety cases opened after selection: **16**
Final holdout accessed: **no**

Baseline: 65/72 exact, 5 wrong automatic edits, 44 upper-clamped candidate scores.
Selected: 71/72 exact, 0 wrong automatic edits, 0 upper-clamped candidate scores.
Independent safety result: 16/16 exact, 0 wrong automatic edits.
Gate: **safety_pass**

The safety corpus was evaluated only after the calibration-only selection was fixed. It did not choose among candidates.

## Selected constants

```json
{
  "context_transform": "legacy_power_035",
  "lexical_weight": 0.7,
  "authorization_weight": 0.14,
  "context_weight": 0.1,
  "phonetic_weight": 0.0,
  "asr_alternative_weight": 0.05,
  "learned_asr_weight": 0.21,
  "negative_context_weight": 1.0,
  "apply_threshold": 0.89,
  "suggest_threshold": 0.72
}
```

## Visible calibration failures

- `cal-context-positive-02-02`: expected apply / `Review Aiven service alerts before the migration.`, got suggest / `Review Ivan service alerts before the migration.`.
- `cal-asr-alternative-02`: expected abstain / `Open the monitoring overview.`, got suggest / `Open the monitoring overview.`.
- `cal-asr-alternative-03`: expected abstain / `Open the monitoring overview.`, got suggest / `Open the monitoring overview.`.
