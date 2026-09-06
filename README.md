# LexiTrace

LexiTrace is a local-first, inspectable personal word-memory prototype for Kivi. It answers the
backend-focused **The Words Kivi Keeps** assignment, not the Golden Goose track. It learns
canonical spellings and their observed variants, then chooses to apply, suggest, or abstain when
similar text appears later.

## Current milestone: 0.6.0

The first vertical slice is implemented:

- explicit teaching with global or learned-context scope;
- correction observation that creates unconfirmed candidates;
- persisted SQLite memories, variants, observations, and decision traces;
- observation-backed positive and negative context evidence with source provenance;
- explicit safety blockers instead of hidden score caps;
- decision-score traces that separate evidence strength from permission to edit;
- positive and negative semantic context prototypes stored per observation;
- a local ONNX embedding adapter with deterministic sparse fallback;
- optional ASR N-best alternatives aligned back to safe editable spans;
- memory inspection, editing, deletion, and per-user reset APIs;
- React interface for teaching, inference, memory state, and score traces;
- Alembic migrations, seed script, Docker Compose, and integration tests;
- exact, fuzzy, and phonetic candidate generation with short-token safety gates;
- immutable memory version history and decision feedback that can demote unsafe memories;
- reproducible 28-case smoke benchmark with no-memory and naive-dictionary baselines;
- fixed 252-case robustness corpus with predeclared calibration and held-out splits;
- per-case input, expected/actual output, memory provenance, model use, cost, storage, and trace;
- chronological journey evaluation with a sparse-context ablation;
- fully documented native reviewer path, optional Docker path, and executable submission preflight.

## Product rule

Retrieval is not permission to edit. A memory must be confirmed, score above the apply threshold,
have sufficient learned context when scoped contextually, survive contradictory evidence, and beat
overlapping alternatives by a safe margin. Manual context lists remain API-level advanced overrides;
the default product path learns context from correction examples and feedback. Semantic similarity
can provide evidence when later language shares meaning but no literal context words. The sparse
profile remains active for explanation and graceful degradation.

## Development

See [RUN.md](RUN.md) for the exact local and Docker workflows and
[docs/architecture.md](docs/architecture.md) for the decision flow, safety policy, and current
limitations. [docs/model.md](docs/model.md) documents the local model, data flow, licenses, and
operational fallback. [docs/evaluation.md](docs/evaluation.md) defines the benchmark method, and
[docs/brief-alignment.md](docs/brief-alignment.md) records the assignment boundary and guardrails.

## AI use

Generative AI was used only as a limited coding assistance tool during the development of this work, primarily for minor programming-related support and clarification. The major conceptual work, system design, implementation, analysis, calculations, technical decisions, and evaluation were carried out independently by the candidate. All design choices, assumptions, results, and conclusions were determined and verified by the candidate. The final work, including any code developed with limited AI assistance, was reviewed, modified, tested, and validated by the candidate before submission.
