# V7 conflict-context floor experiment

Status: development candidate selected; no production policy change.

## Decision rule

The sweep compares absolute positive-context floors of 0.15, 0.20, 0.25, and 0.30 while holding
nearest-example retrieval, the 0.15 context-advantage rule, score thresholds, and all other policy
settings fixed. Automatic lifecycle transitions are disabled only to isolate conflict arbitration;
positive and negative feedback evidence is still recorded and used.

The selection rule is: require zero wrong interventions, maximize exact output, then choose the
least restrictive floor among tied candidates. This is a development selection rule, not final
holdout certification.

## Sweep result

| Conflict positive floor | Exact output | Action accuracy | Wrong interventions |
|---:|---:|---:|---:|
| 0.15 | 12/13 | 12/13 | 1 |
| 0.20 | 13/13 | 13/13 | 0 |
| 0.25 | 13/13 | 13/13 | 0 |
| 0.30 | 12/13 | 12/13 | 0 |

The development rule therefore carries 0.20 forward. At 0.15, a weak 0.1797 positive similarity
incorrectly resolves an ambiguous collision. At 0.30, a valid contextual winner is withheld.

## Combined regression check

The combined candidate is nearest-example retrieval, fixed authorization during contextual
feedback, and a 0.20 conflict positive floor.

| Suite | Exact output | Action accuracy | Wrong interventions |
|---|---:|---:|---:|
| Smoke | 28/28 | 28/28 | 0 |
| Robustness | 248/252 | 248/252 | 0 |
| Original chronological journeys | 6/6 | 6/6 | 0 |
| Multimodal positive journeys | 6/6 | 6/6 | 0 |
| Semantic safety journeys | 13/13 | 13/13 | 0 |

The robustness result is unchanged from the frozen v6 result. Its historical `heldout` label does
not make it the unopened v7 final holdout; it was already consumed before this experiment.

## Why this still is not promoted

Disabling every automatic lifecycle transition is not a valid product design. The existing
lifecycle evaluation shows that lifecycle behavior is useful for genuine identity contradiction,
explicit suppression, and drift. The experiment only proves that context-specific rejection must
not be treated as equivalent to evidence that the spelling memory itself is false.

The next structural step is to split feedback into contextual rejection and identity contradiction.
Contextual rejection should add negative context evidence without globally demoting a confirmed
identity. Identity contradiction should remain eligible to change memory state. That typed
lifecycle must pass the existing lifecycle suite and the semantic safety chronology together before
the retrieval or conflict candidates can be considered for calibration.
