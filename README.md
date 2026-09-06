# LexiTrace

LexiTrace is a local-first, inspectable personal word-memory prototype for Kivi. It learns
canonical spellings and their observed variants, then chooses to apply, suggest, or abstain when
similar text appears later.

## Current milestone

The first vertical slice is implemented:

- explicit teaching with global or contextual scope;
- correction observation that creates unconfirmed candidates;
- persisted SQLite memories, variants, observations, and decision traces;
- high-confidence intervention, visible suggestion, and contextual abstention;
- memory inspection, editing, deletion, and per-user reset APIs;
- React interface for teaching, inference, memory state, and score traces;
- Alembic migrations, seed script, Docker Compose, and integration tests;
- exact, fuzzy, and phonetic candidate generation with short-token safety gates;
- immutable memory version history and decision feedback that can demote unsafe memories;
- reproducible 28-case smoke benchmark with no-memory and naive-dictionary baselines.

## Product rule

Retrieval is not permission to edit. A memory must be confirmed, score above the apply threshold,
survive negative-context checks, and beat overlapping alternatives by a safe margin.

## Development

See [RUN.md](RUN.md) for the exact local and Docker workflows.

## AI use

Generative AI was used only as a limited coding assistance tool during the development of this work, primarily for minor programming-related support and clarification. The major conceptual work, system design, implementation, analysis, calculations, technical decisions, and evaluation were carried out independently by the candidate. All design choices, assumptions, results, and conclusions were determined and verified by the candidate. The final work, including any code developed with limited AI assistance, was reviewed, modified, tested, and validated by the candidate before submission.
