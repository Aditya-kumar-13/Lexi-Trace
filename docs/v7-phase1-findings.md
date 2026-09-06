# Policy v7 phase 1 findings

These measurements describe the frozen v6 behavior on 280 already-known smoke and robustness
cases. They are structural development evidence, not untouched evaluation results.

## Candidate generation

- 595 direct raw matches became 400 per-variant spans after route deduplication.
- Exact-span pruning reduced those to 231 direct candidates before scoring.
- ASR alternatives produced 24 raw matches, 12 per-variant spans, and 12 aligned spans.
- 242 candidates were scored and 242 unique `(memory_id, start, end)` keys were retained.
- No cross-variant duplicate occurred in these corpora and no retained-key invariant failed.
- A separate integration test deliberately creates two routes to one memory/span and proves that
  only the higher-scoring candidate survives.

The absence of natural cross-variant duplicates is evidence about these corpora, not proof that the
deduplication layer is unnecessary.

## Score saturation

The mean raw score was 0.9975 and the median was 1.0342. Of 242 candidates, 142 (58.7%) exceeded
1.0 before clamping. No candidate hit the lower clamp.

This confirms that the current positive weights frequently destroy marginal-score interpretability.
It does not justify changing weights before structural alternatives and interactions are selected.

## Context behavior

Among retained candidates, context control was:

- semantic: 48;
- sparse: 11;
- exact tie: 2;
- no positive context signal: 181.

Semantic evidence therefore controls 78.7% of the 61 candidates with a non-zero combined positive
context. Sparse evidence is not dead, but it is currently a minority signal.

The static corpora produced no negative-context score contribution and no learned-ASR contribution.
Those components cannot be retained or removed from this artifact; chronological targeted journeys
must measure them separately.

## Contribution activity

| Contribution | Non-zero candidates | Mean contribution |
|---|---:|---:|
| Lexical | 242 | 0.6932 |
| Authorization | 229 | 0.1325 |
| Context | 199 | 0.0769 |
| Phonetic | 222 | 0.0917 |
| ASR alternative | 12 | 0.0032 |
| Learned ASR | 0 | 0.0000 |
| Negative context | 0 | 0.0000 |

These are activity measurements, not causal decision-impact estimates.

## Visible failures

Four of 280 cases did not match the declared output/action, all safely remaining suggestions:

1. Three `Adithya -> Aaditya` cases scored 0.9046 because Metaphone did not recognize the intended
   Indic transliteration relationship. This directly supports an Indic-aware phonetic experiment.
2. One `post grass -> Postgres` case had raw semantic similarity 0.5853, which the configured 0.60
   floor reduced to zero. Its exact and phonetic evidence produced 0.96, but the context eligibility
   gate correctly prevented automatic application.

There were zero wrong automatic interventions. Complete candidate traces are preserved in the
instrumentation failure artifact.

## Latency caution

Cases with one retained candidate were slower than cases with multiple candidates, but this is
confounded: the one-candidate group contains most semantic inference, while multi-candidate cases
are often global memories that skip encoding. Candidate count alone is not a causal latency result.
A controlled multi-candidate benchmark is required before making a batching claim.

## Decisions enabled by this phase

Phase 2 must evaluate, rather than assume:

- a score architecture that rarely or never needs output clamping;
- one-path ASR confidence instead of double contribution;
- current centroids versus bounded stored examples;
- Metaphone versus an Indic-aware graded distance on labeled pairs;
- learned-ASR and negative-context impact on chronological targeted journeys;
- Boolean authorization versus continuous trust after the combined signal architecture is known.

No constants or product decisions were changed during Phase 1 instrumentation.
