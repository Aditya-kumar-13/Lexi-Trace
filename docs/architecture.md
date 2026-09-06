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
9. Attribute feedback to an exact ASR confusion route. Reliability is derived from immutable
   outcome events, not an opaque mutable counter.

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

## Learned ASR reliability

ASR confidence and learned reliability are intentionally separate. The former is supplied by the
provider for one hypothesis. The latter is a Beta posterior derived from user outcomes for the tuple
`(user, memory, provider, model, rank, observed form, canonical form)`. The prior is Beta(1, 3), so
one confirmation cannot imply certainty, and the learned contribution remains disabled until three
distinct decision outcomes exist. Provider or model changes therefore return to cold start.

Feedback can target a visible suggestion by memory and span. Each accepted or rejected target creates
an ordinary observation plus an immutable ASR outcome linked to the original decision. The trace
exposes outcome count, accepts, rejects, posterior mean, activation state, and exact contribution.

## Event-derived memory lifecycle

The memory row stores lifecycle state but not a decision-making confidence value. Trust is rebuilt
from immutable observations using a weighted Beta posterior. Explicit teaching, accepted passive
corrections, confirmed interventions, and rejected interventions have separately versioned evidence
weights. Manual context edits do not affect trust.

Passive promotion requires all three gates: posterior at or above 0.80, at least three positive
events, and at least two distinct masked-context fingerprints. A confirmed memory is demoted when
contradictory evidence moves its posterior below 0.60. Suppression is never automatic. Client event
IDs are unique per user and memory, making observation replay idempotent; decision feedback derives
its event ID from the persisted trace and candidate span.

The API and trace expose alpha, beta, posterior mean, positive and negative event counts, context
diversity, failed gates, source weights, and the policy version. Legacy confidence counters remain
mapped only so older databases can migrate; no product decision reads or mutates them.

## Calibrated policy and shadow execution

Threshold search uses only the predeclared robustness calibration split. A second, independently
frozen smoke corpus acts as a safety constraint rather than another optimization target. A policy
candidate is promotable only when it does not increase wrong interventions or reduce exact matches
on that safety corpus. The generated artifact records input hashes, the complete search space,
baseline and candidate metrics, violations, and explicit rollback boundaries.

An inference request may include a shadow threshold profile. LexiTrace scores candidates once, then
resolves active and shadow winners independently. Only the active policy can modify the returned
transcript. The shadow action, hypothetical output, thresholds, and delta are stored inside the
same immutable decision trace. This makes policy comparison reproducible without changing memory
state or exposing users to an unapproved policy.

Every candidate also receives a counterfactual explanation: the active threshold, its score gap,
blocking conditions, and the minimum condition that would have to change. These explanations are
mechanical descriptions of the actual decision path, not generated prose.

## Safety policy

Retrieval is not permission to edit. The following blockers prevent automatic application:

- `MEMORY_NOT_CONFIRMED`
- `CONTEXT_PROFILE_COLD_START`
- `CONTEXT_EVIDENCE_INSUFFICIENT`
- `NEGATIVE_CONTEXT_EVIDENCE`
- `INSUFFICIENT_WINNER_MARGIN`
- `OVERLAPPING_WINNER`

The numeric decision score is diagnostic, not a probability. Policy v5 retains the conservative
`0.93` apply threshold because the calibration-only `0.90` candidate introduced two wrong edits on
the separate safety corpus. The gate records that rejection instead of hiding it behind a better
single-suite headline.

Thresholds and component weights live in the versioned `lexitrace/policy.toml` file. Every decision
trace records the policy version, so benchmark results can be reproduced and policy changes cannot
silently alter historical interpretation.

## Deliberate exclusions

- A global replacement dictionary is unsafe for ambiguous words.
- Hand-written keyword gates do not generalize and are not the default product path.
- An LLM-only decision engine would be difficult to reproduce, inspect, and run locally.
- A hosted LLM or embedding API is unnecessary; the default semantic encoder runs locally.

## Remaining limitation

The posteriors are deliberately local and uncalibrated across providers. Real deployment data would
be required to select priors by locale or provider and test decay under provider model drift. The
prototype does not claim to recognize speech or estimate acoustic confidence itself.
