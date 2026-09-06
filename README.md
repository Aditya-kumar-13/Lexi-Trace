# LexiTrace

LexiTrace is a local-first, inspectable personal word-memory prototype for Kivi. It answers the
backend-focused **The Words Kivi Keeps** assignment, not the Golden Goose track. It learns
canonical spellings and their observed variants, then chooses to apply, suggest, or abstain when
similar text appears later.

## Current milestone: 1.1.0

The reviewer-ready release includes:

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
- fully documented native reviewer path, optional Docker path, and executable submission preflight;
- provider/model/rank-specific ASR confusion outcomes linked to decisions and observations;
- conservative Beta-posterior reliability that activates only after three independent outcomes;
- feedback on safe suggestions, not only edits that were already auto-applied;
- a frozen chronological ASR-learning suite, no-learning ablation, and precision/coverage curve.
- event-derived memory trust with no mutable confidence percentage;
- idempotent observation ingestion and automatic evidence-gated promotion or demotion;
- a frozen lifecycle suite covering replay, context diversity, contradiction, and suppression.
- counterfactual traces that state the blocker or exact score gap behind every non-intervention;
- request-scoped shadow policies that are evaluated and persisted without changing user output;
- split-safe threshold search constrained by a separate frozen safety corpus;
- an automatic release gate that rejects candidates which improve recall by adding wrong edits.
- deterministic collision groups for surface and phonetic routes shared by multiple memories;
- context-learned conflict resolution with safe suggestions for unresolved ties;
- explicit duplicate-memory merging with transferred aliases and evidence;
- safe application of multiple non-overlapping memories in one transcript;
- portable definition export/import and complete per-user data deletion;
- request IDs, structured validation errors, payload limits, and route-level latency counters;
- SQLite WAL, foreign-key enforcement, and a bounded lock wait for concurrent local requests;
- frozen conflict journeys plus a 500-decision latency and database-growth soak test;
- a disposable one-command reviewer demonstration that never touches the user's database.

## Product rule

Retrieval is not permission to edit. A memory must be confirmed, score above the apply threshold,
have sufficient learned context when scoped contextually, survive contradictory evidence, and beat
overlapping alternatives by a safe margin. Manual context lists remain API-level advanced overrides;
the default product path learns context from correction examples and feedback. Semantic similarity
can provide evidence when later language shares meaning but no literal context words. The sparse
profile remains active for explanation and graceful degradation.

Provider confidence is preserved as an input feature, not presented as calibrated truth. Repeated
accepted and rejected outcomes build a separate reliability estimate for one exact provider, model,
rank, observed form, and canonical form. It cannot override memory-state, context, negative-evidence,
or collision blockers.

Memory trust is a versioned weighted Beta posterior computed from immutable observations. Passive
corrections require three positive events across at least two distinct contexts before automatic
confirmation. Duplicate event IDs contribute nothing, contradictory evidence can demote a memory,
and only the user can suppress one.

Decision thresholds are selected under a two-stage policy gate. The robustness calibration split
may nominate a candidate, but promotion also requires no regression on the frozen smoke safety
corpus. The current calibration-only candidate (`0.90`) recovered two cases but caused two wrong
interventions elsewhere, so the gate rejected it and retained `0.93`. It remains available in
shadow mode to make that trade-off visible without affecting the user-facing transcript.

When several memories share a surface or phonetic route, LexiTrace does not choose by insertion
order. It either finds a sufficient learned-context advantage or returns a visible suggestion. A
user can select the intended candidate, and the resulting evidence can resolve similar future
collisions. Independent, non-overlapping memories may still be applied together.

## Development

See [RUN.md](RUN.md) for the exact local and Docker workflows and
[docs/architecture.md](docs/architecture.md) for the decision flow, safety policy, and current
limitations. [docs/model.md](docs/model.md) documents the local model, data flow, licenses, and
operational fallback. [docs/evaluation.md](docs/evaluation.md) defines the benchmark method, and
[docs/brief-alignment.md](docs/brief-alignment.md) records the assignment boundary and guardrails.

## AI use

Generative AI was used only as a limited coding assistance tool during the development of this work, primarily for minor programming-related support and clarification. The major conceptual work, system design, implementation, analysis, calculations, technical decisions, and evaluation were carried out independently by the candidate. All design choices, assumptions, results, and conclusions were determined and verified by the candidate. The final work, including any code developed with limited AI assistance, was reviewed, modified, tested, and validated by the candidate before submission.
