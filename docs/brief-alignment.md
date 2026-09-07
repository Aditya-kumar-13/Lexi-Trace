# Backend brief alignment

## Chosen assignment

This repository answers **The Words Kivi Keeps**, the backend-focused full-stack assignment. It
does not answer the separate Golden Goose semantic-memory assignment. In particular, it does not
submit a product-positioning statement or product-vision document for Golden Goose.

## Product boundary

LexiTrace begins after speech recognition. Its formatter-context endpoint retrieves a bounded set of
relevant personal spelling hints for the formatting prompt. After the formatter produces a draft,
LexiTrace independently decides whether a span should be changed, suggested, or left alone. The
local semantic encoder is used only to decide whether a word-level spelling memory fits the
surrounding sentence. It does not create factual, episodic, preference, or general-purpose
conversational memory.

The following remain deliberate non-goals:

- implementing speech recognition;
- integrating with production Kivi or depending on Kivi infrastructure;
- answering questions about a user's history;
- remembering arbitrary personal facts or preferences;
- building a general agent or broad tool system;
- silently replacing every occurrence of an ambiguous sound-alike.

## Requirement map

| Brief requirement | Repository evidence |
|---|---|
| Accept learning observations | Explicit-teach and accepted-correction API flows |
| Persist and inspect memory | SQLite schema, Alembic migrations, memory/evidence/history endpoints |
| Accept ASR and formatted text | Inference API and browser journey |
| Place relevant memory into formatting prompt | Bounded `/api/v1/formatter-context` contract |
| Produce memory-aware output | Apply/suggest/abstain decision engine |
| Explain intervention or restraint | Persisted candidate features, blockers, reason codes, and policy version |
| Change or remove memory | Edit, suppress, delete, feedback, and reset flows |
| Avoid demo-only prepared behavior | All visible behavior is derived from database state and model decisions |
| Evaluate useful and harmful intervention | No-memory and naive baselines, intervention precision/recall, wrong edits |
| Preserve per-case evidence | Inputs, expected/actual result, memory provenance, trace, and database snapshot |
| Account for operations | Latency, allocated database bytes, model calls, hosted requests, and API cost |
| Reproduce the review path | Native Windows commands in `RUN.md` and the submission preflight script |

## Guardrails taken from the brief

- The provided Kivi sentence is a format example, not the benchmark. The datasets cover names,
  technical terms, multiword variants, collisions, lifecycle states, boundaries, contextual false
  friends, fuzzy candidates, and ASR alternatives.
- Retrieval never grants permission to edit. Confirmed state, contextual support, contradictory
  evidence, threshold, and overlap checks are separate gates.
- Failures are not removed from generated reports. The fixed robustness corpus intentionally keeps
  difficult misses and false interventions visible.
- The system stays narrow. New work should improve word-memory evidence, safety, inspectability, or
  reproducibility rather than add broader kinds of memory.
- No private credential belongs in the repository. The primary local model requires no API key.
- AI assistance is disclosed in `README.md`; the candidate must review and be able to defend every
  product decision and implementation detail.

## Track-specific AI restriction

The Golden Goose brief prohibits generative AI for its positioning and vision documents. That rule
does not appear in the backend-focused brief and those documents are not part of this submission.
If the chosen assignment changes to Golden Goose, those documents must be written independently by
the candidate and this repository must not be presented as satisfying that track.
