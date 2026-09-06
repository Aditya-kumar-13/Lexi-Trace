# LexiTrace architecture

## Product boundary

LexiTrace starts after speech recognition. It accepts a formatted transcript, retrieves personal
word memories, and decides whether to apply, suggest, or abstain from a spelling correction. It
does not implement ASR and does not depend on Kivi infrastructure.

## Decision flow

1. Generate exact, fuzzy, and phonetic candidates from the user's persisted variants.
2. Extract a bounded context fingerprint around every candidate span.
3. Compare that fingerprint with positive and negative evidence learned from earlier observations.
4. Calculate a decision score from independent match, evidence, phonetic, and context signals.
5. Evaluate explicit blockers. A high score cannot bypass a blocker.
6. Resolve competing and overlapping candidates before rewriting any characters.
7. Persist the decision trace so feedback can be attributed to the memories that acted.

## Observation-backed context

Context evidence is attached to the event that produced it. Accepted corrections and confirmed
interventions create positive evidence. Rejected interventions create negative evidence. Each row
stores its observation ID, polarity, feature type, weight, source type, and source context.

The current 0.3.0 context fingerprint uses distance-weighted tokens and nearby bigrams. These are
learned from correction sentences; they are not source-code conditions. Optional manual context is
retained only as an explicit advanced override and is labeled as such in provenance.

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

## Deliberate exclusions

- A global replacement dictionary is unsafe for ambiguous words.
- Hand-written keyword gates do not generalize and are not the default product path.
- An LLM-only decision engine would be difficult to reproduce, inspect, and run locally.
- Semantic embeddings are deferred until the observation and evaluation foundations can measure
  whether they improve generalization without increasing incorrect interventions.

## Next architectural increment

Milestone 0.4 adds independent candidate-retrieval channels and evaluates retrieval recall apart
from intervention precision. Milestone 0.5 adds a replaceable local semantic encoder while keeping
the deterministic evidence and blocker path as a fallback.
