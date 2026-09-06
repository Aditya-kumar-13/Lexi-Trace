# V7 learned-ASR reliability comparison

Status: exact-route design retained; no production behavior or weight changed.

## Alternatives

The existing estimator keys evidence by provider, model, alternative rank, source form, and target
form. This experiment compares it with two structural alternatives:

- no learned reliability contribution;
- model-route pooling, which keeps provider, model, source, and target fixed but combines ranks.

The model-route alternative is deliberately narrow. Provider and model backoff are excluded because
the existing drift journeys already show that transferring evidence across either boundary is
unsafe. All estimators keep the same skeptical beta prior, three-observation activation minimum,
and learned-ASR weight.

## Evidence

On the existing four-journey suite, exact-route learning reaches 16/16 exact outputs and actions
with zero wrong interventions. Removing learned reliability reaches 15/16, also with zero wrong
interventions. The single recovered case is the repeated, explicitly confirmed
`Adithya -> Aaditya` route; provider drift, model drift, and a negative context remain blocked.

The new development chronology uses genuine N-best alignment. It records three accepted rank-two
outcomes, then evaluates the same source/target route at rank one. A second journey adds three
rejected rank-one outcomes before evaluation.

| Rank-drift system | Exact output | Action accuracy | Wrong interventions |
|---|---:|---:|---:|
| No learned contribution | 1/2 | 1/2 | 0 |
| Exact route | 1/2 | 1/2 | 0 |
| Model-route pooling | 1/2 | 1/2 | 0 |

In the helpful case, pooling raises the candidate from 0.8334 to 0.8848 but does not cross the 0.93
apply threshold. In the contradictory case, the exact rank-one route sees zero accepted and three
rejected outcomes, producing a 0.1429 posterior and a 0.0129 contribution. Pooling combines those
with three accepted rank-two outcomes, producing a 0.4000 posterior and a larger 0.0360
contribution. It still does not cause a wrong edit in this dataset, but it discards useful negative
route information without recovering any additional correction.

## Decision

Retain exact-route reliability. Removal gives up a demonstrated safe recovery; rank pooling adds no
coverage and weakens the meaning of contradictory evidence. The rank-drift miss remains an explicit
limitation rather than a reason to relax the evidence key prematurely.

`asr_reliability_mode` is available only as an internal evaluation parameter and defaults to
`exact_route`. The earlier ASR-confidence experiment remains separate: its single-path formulation
improves provenance but did not change an outcome and increased score saturation, so it also remains
unselected.

The two scored rank-drift cases are exploratory development evidence, not a final accuracy claim.
Any future backoff design must demonstrate a real coverage gain on a broader labeled set while
preserving zero wrong interventions across drift and context-abuse cases.
