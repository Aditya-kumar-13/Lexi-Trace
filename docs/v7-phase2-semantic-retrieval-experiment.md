# Policy v7 semantic retrieval experiment

This evaluation-only experiment tests whether multiple valid contexts should be represented by one
weighted centroid or compared with stored examples. The active policy remains centroid-based.

## Coverage defect found first

The original semantic journeys contained effectively one positive vector at each decision, making
centroid and example retrieval identical. Two new chronological development journeys therefore add
three distinct positive contexts for `Kivi` and `Aaditya` before querying engineering, marketing,
legal, travel, and family contexts.

## Compared aggregations

- Weighted centroid: cosine similarity against the weighted mean vector.
- Mean of the three nearest examples: weighted mean of individual cosine similarities.
- Nearest example: maximum individual cosine similarity.

All use the same stored model-versioned vectors and identical events.

## Results

Across six multimodal queries:

- centroid: 6/6 exact outputs and actions, zero wrong interventions;
- mean of three nearest examples: 1/6, zero wrong interventions;
- nearest example: 6/6 exact outputs and actions, zero wrong interventions;
- sparse-only ablation: 0/6, zero wrong interventions.

The mean-of-three alternative is rejected as an aggregation rule: it diluted the relevant example
with unrelated valid contexts. Centroid and nearest-example retrieval remain unresolved because
both pass this small development suite. Negative-context and collision cases are required before
selection. Nearest-example storage also requires the cap and deterministic retention policy defined
in the v7 Definition of Done.
