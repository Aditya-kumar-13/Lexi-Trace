# V7 bounded semantic storage experiment

Status: cap-12 design selected for the structural candidate; product default remains unbounded.

## Storage contract

Nearest-example retrieval is only viable with bounded, auditable evidence. The candidate contract is:

- at most 12 embeddings per memory and polarity across all model versions;
- exact duplicate detection on the normalized, term-masked context within the same model;
- duplicate detection before embedding execution, so replay consumes neither storage nor model work;
- model identifier and vector dimension retained on every row;
- retrieval uses only vectors from the active model with matching dimensions;
- the active model's evidence receives retention priority, while older-model rows fill unused slots
  and are displaced one-for-one as evidence for the new model arrives;
- within the active model, select the highest-reliability deterministic hash seed, then greedily
  retain the context with the greatest minimum cosine distance from the selected set; ties resolve
  by reliability and context hash.

This makes replay deterministic for the same ordered event stream. Two independent memories fed the
same 16 unique contexts retain exactly the same 12 masked contexts in the unit test. Model-rollover
coverage verifies that three new-model examples produce a 3/9 new/old split while the total remains
12. Old-model vectors are ignored by retrieval rather than silently compared across incompatible
spaces.

## Stress result

The development journey records 18 observations spanning 16 unique product contexts, including two
exact context replays, then scores eight unseen paraphrases.

| Storage mode | Semantic rows | Vector payload | Exact output | Wrong interventions |
|---|---:|---:|---:|---:|
| Unbounded | 18 | 145,419 bytes | 8/8 | 0 |
| Cap 12 | 12 | 96,904 bytes | 8/8 | 0 |

The cap reduces vector payload by 48,515 bytes (33.4%) in this stress case with no behavioral loss.
For the 384-dimensional local model used here, the observed full-cap payload is 96,904 bytes per
memory/polarity. A conservative serialization bound of 32 bytes per float plus separators is 152,076
bytes per polarity and 304,152 bytes for a memory with both stores full. SQLite page allocation
falls from 626,688 to 573,440 bytes in the one-memory run; page reuse means allocated-file size is
not expected to shrink in direct proportion to live payload.

The same cap preserves 13/13 semantic-safety queries and 6/6 multimodal positive queries with zero
wrong interventions. Focused tests cover the cap, duplicate replay, zero duplicate embedding calls,
deterministic replay, and model rollover.

## Operational behavior

The cap is enforced only when a new semantic observation is written; enabling it on an existing
oversized memory reduces that polarity to 12 at the next non-duplicate observation. Sparse context
evidence and immutable observations are not deleted, so provenance remains intact. If the semantic
encoder is unavailable or its model does not match stored rows, retrieval continues through the
documented sparse path.

The internal `semantic_evidence_cap` evaluation parameter is `None` by default. Promotion to a
versioned v7 policy waits for combined re-instrumentation, calibration, the safety gate, and the
sealed final holdout.
