# LexiTrace architecture

## Product boundary

LexiTrace starts after speech recognition. It accepts a formatted transcript, retrieves personal
word memories, and decides whether to apply, suggest, or abstain from a spelling correction. It
does not implement ASR and does not depend on Kivi infrastructure.

## Decision flow

1. Generate exact, fuzzy, and phonetic candidates from the user's persisted variants.
2. Extract a bounded context fingerprint around every candidate span.
3. Retrieve additional evidence from aligned ASR N-best alternatives when supplied.
4. Compare sparse fingerprints and semantic vectors with positive and negative prototypes.
5. Calculate a decision score from independent match, evidence, phonetic, ASR, and context signals.
6. Evaluate explicit blockers. A high score cannot bypass a blocker.
7. Resolve competing and overlapping candidates before rewriting any characters.
8. Persist the decision trace so feedback can be attributed to the memories that acted.

## Observation-backed context

Context evidence is attached to the event that produced it. Accepted corrections and confirmed
interventions create positive evidence. Rejected interventions create negative evidence. Each row
stores its observation ID, polarity, feature type, weight, source type, and source context.

The sparse context fingerprint uses distance-weighted tokens and nearby bigrams. These are
learned from correction sentences; they are not source-code conditions. Optional manual context is
retained only as an explicit advanced override and is labeled as such in provenance.

Version 0.5.0 also masks the remembered surface form and encodes the surrounding sentence with a
local ONNX model. Weighted centroids form positive and negative prototypes per memory. The trace
shows raw semantic similarity, prototype margin, observation counts, sparse similarity, and the
model version. Semantic failure never removes the deterministic fallback.

ASR alternatives are treated as retrieval evidence, not editable output. Candidate spans found in
an alternative are token-aligned back to the formatted transcript, and acoustic confidence becomes
one visible feature in the same decision policy.

## Safety policy

Retrieval is not permission to edit. The following blockers prevent automatic application:

- `MEMORY_NOT_CONFIRMED`
- `CONTEXT_PROFILE_COLD_START`
- `CONTEXT_EVIDENCE_INSUFFICIENT`
- `NEGATIVE_CONTEXT_EVIDENCE`
- `INSUFFICIENT_WINNER_MARGIN`
- `OVERLAPPING_WINNER`

The numeric decision score is diagnostic, not a calibrated probability. Probability calibration is
planned for milestone 0.6, after a held-out journey dataset exists.

Thresholds and component weights live in the versioned `lexitrace/policy.toml` file. Every decision
trace records the policy version, so benchmark results can be reproduced and policy changes cannot
silently alter historical interpretation.

## Deliberate exclusions

- A global replacement dictionary is unsafe for ambiguous words.
- Hand-written keyword gates do not generalize and are not the default product path.
- An LLM-only decision engine would be difficult to reproduce, inspect, and run locally.
- A hosted LLM or embedding API is unnecessary; the default semantic encoder runs locally.

## Next architectural increment

The next increment separates retrieval-recall evaluation from intervention precision, adds learned
ASR confusion statistics, and calibrates action thresholds on held-out chronological journeys.
