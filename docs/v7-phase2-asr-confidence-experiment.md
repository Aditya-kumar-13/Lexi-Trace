# Policy v7 ASR confidence experiment

This experiment compares the legacy confidence path with an evaluation-only single-path design on
the 28-case smoke and 252-case robustness development corpora. No live default changed.

## Compared designs

The legacy design allows ASR confidence to substitute for lexical similarity and also adds a
separate ASR-confidence contribution.

The alternative aligns the actual matching surface from the ASR hypothesis, multiplies that lexical
similarity by provider confidence, and removes the separate additive confidence term. Phonetic
agreement is evaluated against the hypothesis surface rather than the different formatted span.

## Results

- 280 cases compared;
- zero changed actions;
- zero changed outputs;
- zero newly fixed cases;
- zero newly broken cases;
- zero wrong interventions in either system.

For the twelve ASR-alternative candidates:

- six high-confidence cases moved from 0.99 to the 1.00 clamp and remained `apply`;
- six low-confidence cases moved from 0.52 to 0.59 and remained `abstain`.

Across all candidates, upper-clamp incidence increased from 142 to 148 and mean raw score increased
from 0.9975 to 1.0002. The alternative removes confidence double-counting but makes hypothesis-level
phonetic evidence explicit, so it does not solve overall score saturation.

## Status

No winner is selected. The alternative is conceptually cleaner about the provenance of lexical
evidence, but it has zero final-action impact on these corpora and increases clamp incidence. It must
be evaluated on targeted ASR abuse and learned-reliability journeys before the retention rule can be
applied.
