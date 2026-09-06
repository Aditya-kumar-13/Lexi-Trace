# Backend-Focused Full-Stack Master Plan

## Project concept

**Working name:** LexiTrace - Personal Word Memory for Kivi

**One-line product claim:** After a user teaches a personal word, LexiTrace writes it correctly in future, relevant transcripts; when the evidence or context is ambiguous, it abstains, and every decision can be traced to its source observations.

**Positioning statement:** LexiTrace remembers only the words a user deliberately teaches or repeatedly corrects. It applies a memory only when the evidence, pronunciation, and context agree. Every intervention is visible, attributable, reversible, and testable. The goal is not to correct the most text. It is to make personal language reliable without turning the user into the administrator of an AI system.

This plan deliberately targets the backend-focused assignment. It does not require Kivi source code, Kivi APIs, real speech recognition, or a hosted service. The complete system runs locally and accepts simulated ASR and formatted text.

---

## 1. What will make this submission distinctive

The submission should demonstrate six qualities at the same time:

1. **Product restraint:** It solves personal word memory rather than drifting into general semantic memory.
2. **Trustworthy learning:** A correction does not automatically become an unsafe global find-and-replace rule.
3. **High-precision intervention:** Ambiguous cases produce a suggestion or abstention instead of an incorrect silent edit.
4. **Complete inspectability:** Every memory and output change has evidence, feature scores, thresholds, and an explanation.
5. **Serious evaluation:** The benchmark includes adversarial negatives, baselines, ablations, calibration, latency, storage, and visible failures.
6. **Reviewer-grade reproducibility:** One documented command starts the application; one command runs the evaluation; one command resets it.

The memorable idea should be **progressive trust**:

- LexiTrace can notice a correction.
- It can propose a candidate memory.
- It can require confirmation when evidence is weak.
- It can automatically apply only mature, unambiguous memories.
- It can preserve a negative decision such as “do not change kiwi when discussing fruit.”

This produces a richer product than a dictionary while remaining tightly within phonetic memory.

---

## 2. Scope and non-goals

### In scope

- Accept raw ASR output and already-formatted output.
- Accept explicit teaching and corrected final transcripts as learning evidence.
- Derive candidate word or phrase memories from minimal text differences.
- Store canonical spellings, observed variants, confidence, context, provenance, and history.
- Retrieve candidate memories for new transcripts.
- Apply, suggest, or abstain using a calibrated decision policy.
- Handle one-word and multiword personal terms.
- Explain every learning and inference decision.
- Confirm, edit, suppress, delete, export, import, and reset memory.
- Run a reproducible evaluation and produce machine-readable and human-readable reports.
- Provide an optional formatter/model adapter without making the default review path dependent on paid credentials.

### Explicit non-goals

- Building speech recognition.
- Reproducing the production Kivi interface.
- General grammar correction.
- General autocorrect.
- Episodic or semantic memory.
- Inferring sensitive facts about the user.
- Crawling contacts, email, or private applications.
- Training a custom language model.
- Making an external LLM mandatory for the primary evaluation.

These non-goals should appear in the README because they demonstrate judgment.

---

## 3. The primary user journeys

### Journey A: Explicit teaching

1. The user opens **Teach**.
2. They enter or select:
   - ASR: `schedule with aditya from sarvam`
   - Formatted: `Schedule with Aditya from Sarvam.`
   - Accepted correction: `Schedule with Aaditya from Sarvam.`
3. LexiTrace highlights the minimal change: `Aditya -> Aaditya`.
4. It proposes a memory:
   - canonical form: `Aaditya`
   - observed form: `Aditya`
   - likely type: person name, if explicitly supplied; otherwise unknown
   - evidence: correction event and full source transcript
5. Because the user explicitly taught it, the memory becomes confirmed immediately.
6. The user sees exactly what future text may change and can narrow or broaden the context.

### Journey B: Passive correction observation

1. A formatted transcript and the user-accepted final text differ.
2. LexiTrace aligns the texts and extracts minimal spans.
3. Punctuation-only, whitespace-only, broad rewrites, and ordinary grammar edits are rejected as non-memory evidence.
4. A small personal-looking correction becomes a candidate.
5. One weak observation does not silently activate it.
6. A second consistent observation increases confidence; the interface asks for confirmation or activates it only if the configured policy and evidence justify that decision.

### Journey C: Safe intervention

1. New formatted text contains `Sarvam Kiwi service`.
2. Retrieval finds canonical `Kivi` with observed variant `Kiwi`.
3. The engine evaluates:
   - word-boundary match;
   - edit and phonetic similarity;
   - contextual compatibility with `Sarvam` and `service`;
   - memory maturity;
   - negative contexts;
   - gap between the best and second-best candidates.
4. A high score produces `Sarvam Kivi service`.
5. The output highlights the change and links it to the source correction.

### Journey D: Correct abstention

1. New text says `Add kiwi fruit to the shopping list.`
2. The same `Kiwi -> Kivi` candidate is retrieved.
3. Fruit-related context conflicts with the learned work context.
4. The score remains below the intervention threshold.
5. The output stays unchanged.
6. The explanation states that a memory was considered but rejected because its context was incompatible.

### Journey E: Conflict and user control

1. Two memories could match `Jon`: `John` and `Jonn`.
2. Neither has a sufficient winner margin.
3. LexiTrace abstains or offers a visible suggestion.
4. The user can resolve the conflict, scope the entries, or suppress one variant.
5. The memory-version history preserves the change and supports undo.

### Journey F: Deletion and reset

1. The user deletes a memory.
2. The memory no longer affects inference immediately.
3. Its personal content is removed according to the documented deletion policy.
4. A full reset returns the application to a deterministic empty state.
5. The reviewer can reseed the demonstration with one command.

---

## 4. Product surfaces

Build a compact but polished browser interface with six routes.

### 4.1 Guided demo

The landing page should offer a 90-second reviewer journey:

1. Load the `Aaditya / Kivi / kiwi fruit` scenario.
2. Teach two terms.
3. Run one positive and one negative inference.
4. Open the explanation trace.
5. Open the benchmark dashboard.
6. Reset the system.

This removes uncertainty about what the reviewer should try.

### 4.2 Teach

- Three side-by-side text areas: ASR, formatted, accepted final.
- Inline diff with token spans.
- Extracted candidate cards.
- Evidence-strength indicator.
- Confirm, reject, or edit before storage.
- Optional metadata: application, domain, term type, timestamp.
- A plain-language explanation of why an edit did or did not qualify as memory.

### 4.3 Playground

- ASR and formatted inputs.
- Memory-aware output.
- Change highlights.
- Apply/suggest/abstain badge.
- Total and stage-level latency.
- Candidate list with expandable score breakdown.
- “View source evidence” link.
- “This is wrong” action that creates counter-evidence and supports immediate undo.

### 4.4 Memory library

- Search and filters by status, type, confidence, last used, and source.
- Each row shows canonical form, observed variants, status, evidence count, and last intervention.
- Detail view shows contexts, negative contexts, provenance, version history, and recent decisions.
- Confirm, edit, merge, suppress, delete, and export actions.
- Candidate/confirmed/suppressed/conflicted visual states.

### 4.5 Decision inspector

Display a waterfall-style trace:

1. normalized input;
2. generated spans;
3. retrieved memories;
4. feature values per candidate;
5. exclusions and rule failures;
6. raw score and calibrated confidence;
7. best-versus-runner-up margin;
8. applicable threshold;
9. final action and output diff;
10. source evidence links.

This is the signature interface. It converts “AI magic” into an inspectable engineering system.

### 4.6 Evaluation dashboard

- Overall metrics and confidence intervals.
- Results by scenario category and term type.
- Confusion matrix for intervene versus abstain.
- Precision-recall curve across thresholds.
- Calibration diagram.
- Baseline and ablation comparison.
- p50/p95/p99 latency.
- database growth and bytes per active memory.
- complete failure table with filters and reproducible case IDs.
- links from every case to its inference trace.

---

## 5. Learning model

### 5.1 Supported evidence types

Use an explicit evidence hierarchy:

| Evidence | Reliability | Default effect |
|---|---:|---|
| User explicitly teaches a canonical term and variant | 1.00 | Confirm immediately |
| User confirms a proposed memory | 1.00 | Confirm immediately |
| User corrects an intervention | 1.00 counter-evidence | Undo, reduce/suppress the bad mapping |
| Accepted final transcript contains a small correction | 0.70 | Create/update candidate |
| Same correction repeats in an independent context | 0.80 | Raise maturity; potentially request confirmation |
| Imported user dictionary entry | configurable | Confirm or stage depending on import source |
| Model-only inference | at most 0.30 | Never activate by itself |

Do not hard-code these final weights without validation. Treat them as initial values, tune them on a development set, and freeze them before the held-out evaluation.

### 5.2 Difference extraction

Align formatted and accepted-final text at token and character levels.

Produce minimal edit spans using edit operations rather than comparing entire sentences. A span is eligible only when it satisfies defined constraints, for example:

- one to four tokens;
- bounded edit distance;
- not punctuation-only;
- not whitespace-only;
- not primarily sentence restructuring;
- not a common grammar or capitalization-only correction unless the canonical casing itself is explicitly taught;
- no overlap with a larger unrelated rewrite;
- source and destination both contain meaningful alphanumeric content.

Store rejected observations as inspectable records with reason codes such as:

- `PUNCTUATION_ONLY`
- `GENERAL_REWRITE`
- `SPAN_TOO_LARGE`
- `LOW_INFORMATION`
- `CONTRADICTORY_EVIDENCE`
- `AMBIGUOUS_ALIGNMENT`

### 5.3 Memory state machine

Use explicit state transitions:

`candidate -> confirmed -> suppressed -> deleted`

Additional transition states may be `conflicted` and `merged`, but they must not complicate the primary workflow.

- **candidate:** observed but not trusted for silent intervention.
- **confirmed:** eligible for automatic intervention when inference confidence is high.
- **suppressed:** retained for audit but cannot intervene.
- **conflicted:** two or more incompatible canonical forms compete without a safe winner.
- **deleted:** excluded from all active indexes and removed according to the deletion policy.

Every transition creates an immutable version/audit event containing actor, timestamp, reason, previous state, and new state.

### 5.4 Confidence and maturity

Separate three concepts that weaker implementations often collapse:

- **Evidence confidence:** How strongly do observations support this mapping?
- **Context compatibility:** Does this memory belong in the current phrase?
- **Decision confidence:** Is intervention safe in this particular transcript?

A mature memory can still be rejected in an incompatible context. This is essential to the `Kivi` versus `kiwi fruit` story.

---

## 6. Retrieval and decision engine

### 6.1 Candidate generation

Generate bounded one- to four-token spans from the formatted transcript. Preserve original character offsets so replacements do not corrupt punctuation or spacing.

Retrieve memories through multiple channels:

1. exact normalized variant match;
2. canonical/alias prefix or phrase match;
3. phonetic-key match;
4. edit-similarity match;
5. context keyword match;
6. prior successful match in the same application or domain.

Candidate generation should favor recall. The later decision policy provides precision.

### 6.2 Features

Record every feature used by the decision:

- exact variant match;
- normalized edit similarity;
- Damerau-Levenshtein or Indel similarity;
- phonetic-key agreement;
- token count agreement;
- canonical/variant length ratio;
- left-context compatibility;
- right-context compatibility;
- application/domain compatibility;
- memory state and maturity;
- number and reliability of supporting observations;
- contradictory-evidence count;
- negative-context match;
- recency only where product reasoning justifies it;
- ambiguity margin between the best and second-best candidates;
- whether the replacement would be a no-op;
- whether the match crosses a word boundary.

Use fuzzy and phonetic signals for candidate discovery, not as independent permission to rewrite text. RapidFuzz provides optimized string-similarity functions, while Jellyfish supplies phonetic encoders such as Metaphone; both are useful ingredients, not product policy.

### 6.3 Decision policy

Use three outcomes:

- **Apply:** high confidence and sufficient winner margin.
- **Suggest:** plausible but requires user confirmation.
- **Abstain:** insufficient, conflicting, suppressed, or contextually incompatible evidence.

Initial threshold proposal:

- `apply >= 0.93`
- `suggest >= 0.72 and < 0.93`
- `abstain < 0.72`
- require best-minus-second-best margin of at least `0.12` for silent application

These are hypotheses, not final numbers. Select thresholds on the development split to satisfy a false-intervention constraint, then lock them before running the test split.

### 6.4 Replacement safety

- Apply replacements by stored character spans from right to left.
- Never use unrestricted substring replacement.
- Preserve punctuation and surrounding whitespace.
- Define deterministic overlap resolution for competing spans.
- Prefer a confirmed multiword memory over overlapping single-token memories only when its score and margin qualify.
- Re-run validation after replacement to prevent duplicate or cascading edits.
- Require idempotence: processing memory-aware output again must produce the same output.

### 6.5 Formatter/model boundary

Define a `FormatterPort` interface:

- `DeterministicFormatter`: default, local, no credentials, used by the primary benchmark.
- `PromptPackFormatter`: returns a structured memory context pack that a production formatter could place in its prompt.
- `ExternalModelFormatter`: optional adapter behind an environment variable and feature flag.

The optional model adapter must never be required to start, inspect, reset, or run the primary evaluation. Benchmark it separately and report prompt tokens, latency, cost, and nondeterminism. If it fails to improve results materially, exclude it from the claimed system.

---

## 7. Data model

Use UUIDs, UTC timestamps, foreign keys, explicit enums/check constraints, and migration-managed schema changes.

### Core tables

#### `users`

- `id`
- `display_name`
- `created_at`

The app may ship as single-user, but `user_id` must scope every personal record to prevent cross-user leakage.

#### `transcript_events`

- `id`
- `user_id`
- `raw_asr_text`
- `formatted_text`
- `accepted_text`
- `application`
- `domain`
- `occurred_at`
- `metadata_json`
- `created_at`

#### `observations`

- `id`
- `user_id`
- `transcript_event_id`
- `source_span`
- `target_span`
- `source_offsets`
- `target_offsets`
- `evidence_type`
- `reliability`
- `status`
- `rejection_reason`
- `created_at`

#### `memories`

- `id`
- `user_id`
- `canonical_form`
- `normalized_canonical`
- `term_type`
- `state`
- `evidence_confidence`
- `maturity_level`
- `created_at`
- `updated_at`
- `deleted_at`

#### `memory_variants`

- `id`
- `memory_id`
- `surface_form`
- `normalized_form`
- `phonetic_keys_json`
- `support_count`
- `contradiction_count`
- unique constraint for user/memory/normalized variant as appropriate

#### `memory_evidence`

- `memory_id`
- `observation_id`
- `effect` (`support` or `contradict`)
- `weight`
- `created_at`

#### `memory_contexts`

- `id`
- `memory_id`
- `kind` (`positive`, `negative`, `application`, `domain`)
- `value`
- `weight`
- `source_observation_id`

#### `memory_versions`

- `id`
- `memory_id`
- `version_number`
- `snapshot_json`
- `action`
- `reason`
- `actor`
- `created_at`

#### `decisions`

- `id` / `trace_id`
- `user_id`
- `raw_asr_text`
- `formatted_text`
- `memory_aware_text`
- `action_summary`
- `total_latency_ms`
- `engine_version`
- `configuration_hash`
- `created_at`

#### `decision_candidates`

- `id`
- `decision_id`
- `memory_id`
- `input_span`
- `output_span`
- `feature_json`
- `raw_score`
- `calibrated_confidence`
- `rank`
- `threshold`
- `action`
- `reason_codes_json`
- `latency_ms`

#### `evaluation_runs` and `evaluation_cases`

Persist run configuration, git SHA, dataset hash, thresholds, expected/actual results, metrics, and trace IDs. This makes generated reports auditable rather than disconnected JSON files.

---

## 8. API contract

Use versioned endpoints and generate OpenAPI documentation.

### Learning and inference

- `POST /api/v1/observations/explicit`
- `POST /api/v1/observations/correction`
- `POST /api/v1/infer`
- `GET /api/v1/decisions/{trace_id}`

### Memories

- `GET /api/v1/memories`
- `GET /api/v1/memories/{id}`
- `PATCH /api/v1/memories/{id}`
- `POST /api/v1/memories/{id}/confirm`
- `POST /api/v1/memories/{id}/suppress`
- `POST /api/v1/memories/{id}/restore`
- `POST /api/v1/memories/merge`
- `DELETE /api/v1/memories/{id}`

### Data portability and operations

- `POST /api/v1/import`
- `GET /api/v1/export`
- `POST /api/v1/reset`
- `POST /api/v1/seed`
- `GET /api/v1/health`
- `GET /api/v1/ready`

### Evaluation

- `POST /api/v1/evaluations`
- `GET /api/v1/evaluations/{run_id}`
- `GET /api/v1/evaluations/{run_id}/cases`
- `GET /api/v1/evaluations/{run_id}/report`

Every mutating request should return the relevant IDs, new state, version, and an explanation. Every inference returns output text, modifications, considered candidates, reason codes, trace ID, latency, and engine/configuration versions.

---

## 9. Recommended implementation stack

### Primary stack

- **Frontend:** React + TypeScript + Vite.
- **Backend:** Python + FastAPI + Pydantic.
- **Database:** SQLite in WAL mode for the primary local review path.
- **ORM/migrations:** SQLAlchemy 2.x + Alembic.
- **Matching:** RapidFuzz plus Jellyfish phonetic encoders.
- **Tests:** pytest, Hypothesis for property-based checks, and Playwright for the reviewer journey.
- **Packaging:** Docker Compose plus native setup instructions.
- **Reports:** JSON, CSV, and a generated standalone HTML or Markdown report.
- **Instrumentation:** structured JSON logs and internal timers; OpenTelemetry is a stretch layer only if it remains simple.

### Why this stack

- FastAPI gives typed request validation, OpenAPI output, dependency injection, and direct pytest/TestClient integration.
- SQLite keeps setup local and dependable; FTS5 can support inspect/search surfaces, though primary term retrieval should remain purpose-built and measurable.
- Alembic makes schema evolution explicit instead of relying on implicit table creation.
- RapidFuzz and phonetic encoding provide efficient candidate-generation signals.
- Docker offers a uniform reviewer path, while native commands protect against Docker availability issues.

Do not add Postgres, Redis, a vector database, Kafka, or a microservice split unless a measured requirement demands them. For a personal lexicon, they weaken reproducibility without proving better judgment.

---

## 10. Benchmark design

The evaluation is as important as the product. Build two complementary suites.

### 10.1 Curated gold benchmark

Target **600-1,000 manually reviewed inference cases** organized into deterministic learning journeys. Each journey includes ordered observations, resulting memory state, and later inference cases. Do not merely generate independent pairs.

Recommended distribution:

| Category | Approximate share | Purpose |
|---|---:|---|
| Personal names and spelling variants | 18% | Core phonetic memory |
| Organizations, products, and projects | 15% | Domain-specific terms |
| Acronyms and casing | 8% | `api/API`, product capitalization |
| Multiword terms | 10% | Phrase retrieval and overlap |
| Indian names and transliterations | 10% | Relevant linguistic diversity |
| Code/technical identifiers | 8% | `Postgres`, package/project names |
| Positive-context intervention | distributed | Useful corrections |
| Homophones and collisions | 10% | Ambiguity and winner margin |
| Ordinary words resembling memories | 10% | False-intervention pressure |
| Negative context and explicit suppression | 6% | Learned abstention |
| Contradictory/stale evidence | 5% | Memory lifecycle |

Across the complete benchmark, target roughly **55% intervention cases and 45% abstention/no-change cases**. A high negative share prevents an inflated score from a benchmark containing only easy corrections.

Split data by **term or memory journey**, not by individual sentence, to prevent nearly identical variants of the same term leaking across development and test sets.

Suggested split:

- 60% development/tuning;
- 20% validation;
- 20% frozen test;
- an additional sealed adversarial suite written before final threshold tuning.

### 10.2 Property and metamorphic suite

Generate thousands of deterministic variations that test invariants rather than headline accuracy:

- adding punctuation must not change the selected memory;
- unrelated surrounding sentences must not trigger a memory;
- output must be idempotent;
- deleting/suppressing a memory must stop its effects;
- reset must remove every learned effect;
- reordering independent learning events must not change final memory state;
- case normalization must not corrupt canonical casing;
- replacing a token must not alter adjacent punctuation;
- overlapping candidates must resolve deterministically;
- no memory belonging to user A may affect user B;
- every applied change must have at least one active confirmed memory and source observation;
- every decision must produce a trace with a configuration hash.

### 10.3 Baselines

Report at least four systems on the identical frozen test set:

- **B0: No memory** - return formatted output unchanged.
- **B1: Naive dictionary** - unconditional exact/global replacement.
- **B2: Fuzzy-only** - top candidate over a similarity threshold.
- **B3: LexiTrace full system** - evidence, context, margin, state, and negative controls.

The comparison should prove that sophistication reduces harmful interventions, not merely add architectural complexity.

### 10.4 Ablations

Run the full system with one capability removed at a time:

- without context scoring;
- without negative contexts;
- without evidence maturity;
- without top-two ambiguity margin;
- without phonetic candidate retrieval;
- without multiword matching;
- without learned counter-evidence.

The report should explain which component changes which metric and include the failures introduced by its removal.

### 10.5 Metrics

#### Primary product metrics

- **Intervention precision:** useful interventions / all interventions.
- **Intervention recall:** useful interventions / all required interventions.
- **Incorrect intervention rate:** harmful interventions / all cases.
- **Unnecessary intervention rate:** harmless but unjustified changes / all cases.
- **Abstention accuracy:** correct abstentions / all cases requiring no change.
- **Exact sentence match:** complete actual output equals expected output.

#### Retrieval metrics

- candidate recall@1, @3, and @5;
- mean reciprocal rank;
- percentage of required terms not generated as candidates.

#### Calibration metrics

- Brier score;
- expected calibration error;
- reliability diagram;
- precision-recall curve and threshold table.

#### Operational metrics

- p50, p95, and p99 total inference latency;
- p50/p95 latency by pipeline stage;
- cold and warm startup latency;
- database size after 10, 100, 1,000, and 10,000 memories;
- bytes per active memory and per observation;
- import throughput;
- evaluation runtime;
- model calls, tokens, cost, and failure rate, which are zero for the deterministic default.

#### Inspectability metrics

- provenance coverage: percentage of applied changes linked to source evidence;
- trace completeness: percentage of decisions containing all required stages;
- replay equivalence: percentage of stored decisions reproduced identically from the same engine/configuration version.

### 10.6 Aspirational acceptance gates

These are targets to earn through evaluation, not numbers to claim before measurement:

- intervention precision **>= 99.0%** on the frozen gold set;
- incorrect intervention rate **<= 0.5%**;
- recall **>= 95%** on supported use cases;
- abstention accuracy **>= 98%**;
- exact sentence match **>= 96%**;
- candidate recall@5 **>= 99%**;
- provenance and trace completeness **100%**;
- deterministic replay equivalence **100%**;
- p95 local inference latency **< 100 ms** with 10,000 memories on the declared reference machine;
- zero cross-user leakage in tests;
- zero required external API calls in the primary path;
- one-command benchmark and reset both succeed from a clean clone.

If the measured results fall short, report them honestly and explain the dominant failure categories. Credible 96% performance with excellent failure analysis is stronger than an unsupported claim of perfection.

### 10.7 Statistical reporting

- Include numerator and denominator for every percentage.
- Report bootstrap 95% confidence intervals for headline metrics.
- Do not aggregate away important categories.
- Freeze the test dataset and thresholds before the final run.
- Store a dataset hash, configuration hash, engine version, timestamp, environment, and git SHA with every run.
- Never delete or manually hide failing cases from generated results.

---

## 11. Test strategy

### Unit tests

- normalization and Unicode handling;
- token/character alignment;
- minimal diff extraction;
- candidate rejection reason codes;
- phonetic and fuzzy candidate generation;
- score calculation;
- threshold boundaries;
- overlap resolution;
- span replacement;
- state-machine transitions;
- merge, suppression, deletion, undo, and reset;
- serialization and configuration hashing.

### Integration tests

- observation -> memory -> inference -> trace;
- conflicting observations;
- API validation and error contracts;
- transaction rollback;
- migrations from an empty database;
- import/export round trip;
- database reset and deterministic reseed;
- two-user isolation;
- optional formatter unavailable or timing out.

### End-to-end tests

- the documented 90-second reviewer journey;
- one positive intervention;
- one contextual abstention;
- memory edit and immediate behavior change;
- full reset;
- evaluation dashboard loads generated results.

### Property-based tests

- idempotence;
- no out-of-bounds spans;
- preserved untouched text;
- stable results under harmless punctuation variations;
- deterministic result under fixed state/configuration;
- deletion and suppression eliminate active effects;
- output edits always map to active evidence.

### Quality gates

- 100% pass rate on the frozen test and E2E suites;
- high branch coverage for the learning and decision engines, with a practical target of at least 90%;
- type checking for backend and frontend;
- linting and formatting;
- no committed secrets;
- migration check passes;
- Docker and native setup both tested from clean state;
- benchmark output is reproducible within documented tolerances.

---

## 12. Repository structure

```text
lexitrace/
  README.md
  RUN.md
  LICENSE
  .env.example
  docker-compose.yml
  Makefile
  pyproject.toml
  package.json
  apps/
    api/
      lexitrace/
        api/
        domain/
        learning/
        retrieval/
        decision/
        persistence/
        evaluation/
        observability/
      tests/
    web/
      src/
        routes/
        components/
        api/
        design/
      tests/
  migrations/
  data/
    seed/
    benchmark/
      schemas/
      dev/
      validation/
      test/
      adversarial/
  evaluation/
    run.py
    metrics.py
    reports.py
    baselines.py
    ablations.py
  results/
    latest/
      summary.json
      cases.jsonl
      metrics.csv
      report.html
      report.md
  scripts/
    bootstrap.ps1
    bootstrap.sh
    seed.py
    reset.py
    verify_clean_clone.py
  docs/
    architecture.md
    product-decisions.md
    data-contract.md
    evaluation-methodology.md
    limitations.md
    ai-use.md
```

Keep all core business logic independent of FastAPI handlers and database classes so it can be unit-tested and replayed deterministically.

---

## 13. Import format

Document a JSONL format so reviewers can supply new cases without touching code.

Example learning event:

```json
{
  "event_id": "obs-001",
  "user_id": "demo-user",
  "raw_asr": "ask aditya to review the sarvam kiwi service",
  "formatted": "Ask Aditya to review the Sarvam Kiwi service.",
  "accepted": "Ask Aaditya to review the Sarvam Kivi service.",
  "application": "slack",
  "occurred_at": "2026-08-01T10:00:00Z"
}
```

Example inference case:

```json
{
  "case_id": "case-001",
  "user_id": "demo-user",
  "raw_asr": "send the sarvam kiwi service notes",
  "formatted": "Send the Sarvam Kiwi service notes.",
  "expected": "Send the Sarvam Kivi service notes.",
  "expected_action": "apply",
  "category": "product-name-positive"
}
```

Validate imports against a versioned JSON Schema and return line-specific errors.

---

## 14. Observability and privacy

### Observability

- Generate a trace ID for every inference.
- Time normalization, candidate generation, retrieval, scoring, replacement, and persistence separately.
- Use structured logs with event names and IDs rather than raw personal text by default.
- Provide a debug mode that includes full text only when explicitly enabled.
- Record engine version and configuration hash.
- Add a `/health` check for process health and `/ready` for database/migration readiness.

OpenTelemetry can be added for local traces if it remains unobtrusive, but a clear built-in decision trace is more important than infrastructure telemetry.

### Privacy and control

- Local storage by default.
- No external call in the core path.
- User-scoped database queries everywhere.
- Clear export and delete controls.
- Redacted logs by default.
- No learning from rejected suggestions unless the user explicitly confirms the feedback.
- No storage of audio because the task operates on text.
- Document the difference between soft suppression for audit and hard deletion for privacy.

---

## 15. Delivery phases

### Phase 0 - Freeze the claim and contracts (Day 1)

- Write the one-line claim and non-goals.
- Define supported evidence types and outcomes.
- Define JSONL schemas and benchmark categories.
- Create 30 “north-star” cases before implementation.
- Record expected behavior and reason codes.

**Exit gate:** A reviewer can understand exactly what success and abstention mean.

### Phase 1 - Walking skeleton (Days 2-3)

- Repository, CI, backend, frontend, database, migrations.
- Health/readiness endpoints.
- Create/read memory flow.
- Empty-state playground.
- Docker and native bootstrap.
- Initial reset/seed commands.

**Exit gate:** Clean clone can start, migrate, seed, open, and reset.

### Phase 2 - Learning engine (Days 4-6)

- Alignment and minimal edit extraction.
- Eligibility filters and reason codes.
- Evidence persistence.
- Memory state machine and versions.
- Explicit teach and passive correction flows.
- Unit/property tests.

**Exit gate:** Corrections reliably create candidates or documented rejections.

### Phase 3 - Retrieval and intervention (Days 7-9)

- Span generation.
- Exact, fuzzy, and phonetic retrieval.
- Context/negative-context features.
- Decision score and three outcomes.
- Safe replacement and overlap handling.
- Complete decision traces.

**Exit gate:** North-star positive, negative, collision, and multiword cases pass.

### Phase 4 - User control and inspector (Days 10-11)

- Memory list/detail.
- Confirm, edit, suppress, merge, delete, and undo.
- Decision waterfall.
- Source evidence navigation.
- Import/export.

**Exit gate:** Every behavior-changing state is visible and reversible.

### Phase 5 - Evaluation system (Days 12-15)

- Curated journeys and held-out splits.
- Baselines and ablations.
- Metrics, confidence intervals, latency/storage measurements.
- Property/metamorphic cases.
- Failure explorer and reports.
- Freeze thresholds before final test.

**Exit gate:** One command produces all cases and reports without editing files.

### Phase 6 - Polish and hardening (Days 16-18)

- 90-second guided demo.
- Responsive/accessibility pass.
- API errors and empty states.
- Cross-platform scripts.
- Clean-clone rehearsals.
- README, RUN.md, architecture, limitations, AI use.

**Exit gate:** A fresh reviewer machine can complete every required operation without interpretation.

### Phase 7 - Final evidence pass (Days 19-20)

- Run full CI and frozen benchmark from the final commit.
- Generate and commit final reports.
- Record final git SHA and environment.
- Verify no secrets or local-only paths.
- Test every command copied directly from RUN.md.
- Capture a short demo video or GIF as optional supplementary material, never as a substitute for a runnable app.

**Exit gate:** The exact submitted SHA is the exact reviewed and benchmarked SHA.

---

## 16. Must-have, differentiator, and stretch priorities

### Tier 1 - Non-negotiable

- Complete teach/infer/inspect/reset journey.
- Durable SQLite storage and migrations.
- Exact provenance.
- Apply/suggest/abstain policy.
- Negative cases and ambiguity handling.
- Reproducible benchmark with visible failures.
- Strong RUN.md.

### Tier 2 - Selection differentiators

- Memory state machine and version history.
- Contextual abstention.
- Top-two ambiguity margin.
- Counter-evidence and negative memories.
- Decision waterfall.
- Baseline and ablation studies.
- Calibration and confidence intervals.
- Metamorphic/property tests.
- Guided reviewer journey.
- Import/export schema.

### Tier 3 - Stretch only after Tier 1 and 2 are excellent

- Optional model/formatter adapter and separate comparison.
- OpenTelemetry trace export.
- Memory merge suggestions.
- Batch corpus importer with progress reporting.
- Performance test at 100,000 memories.
- Accessibility audit and keyboard-complete interface.
- Small demo video.

Do not implement a stretch feature if it threatens test quality, docs, or clean-clone reproducibility.

---

## 17. README structure

1. Product claim and 30-second explanation.
2. Demo screenshots/GIF and primary interactions.
3. What the system learns and refuses to learn.
4. Architecture diagram.
5. Learning and inference algorithms.
6. Memory lifecycle and user control.
7. Evaluation methodology and data splits.
8. Headline results with denominators and links to full reports.
9. Failure analysis.
10. Performance, storage, and cost.
11. Privacy and security choices.
12. Limitations and production integration boundary.
13. AI/tool use disclosure.
14. Link to RUN.md.

### Architecture diagram

```text
ASR text + formatted text + accepted correction
                     |
                     v
          Alignment / observation filter
                     |
                     v
        Evidence ledger -> Memory state machine
                              |
New ASR + formatted text       v
              |       Personal lexicon store
              v                |
        Span generation <------+
              |
      Multi-channel retrieval
              |
       Feature computation
              |
   Apply / Suggest / Abstain
              |
   Safe span replacement + trace
              |
 Memory-aware output + explanation
```

---

## 18. RUN.md requirements

Start with a bold declaration:

> **Primary review method: Local Docker Compose application using an embedded SQLite database. No external model key is required.**

Then provide, in exact order:

1. supported OS/runtime versions;
2. prerequisites;
3. environment variables and `.env.example` instructions;
4. exact install/build command;
5. exact migration and seed command;
6. exact start command;
7. URL to open;
8. 90-second primary interactions;
9. exact evaluation command;
10. output report paths;
11. memory/database inspection instructions;
12. import procedure and JSONL schema link;
13. exact reset command;
14. stop/cleanup command;
15. troubleshooting limited to known, tested issues;
16. native fallback path.

Every command in RUN.md must be copied into a clean environment and executed exactly as written before submission.

---

## 19. Likely failure modes to design against

- Treating every edit as a personal memory.
- Global replacement that changes substrings or ordinary words.
- A benchmark containing almost no negative cases.
- Tuning on the final test set.
- Random train/test splitting that leaks the same names across splits.
- Reporting only aggregate accuracy.
- Hiding failures or selecting examples after implementation.
- Adding an LLM whose nondeterminism makes evaluation irreproducible.
- Requiring a paid key for the primary path.
- Storing a confidence score without showing how it was produced.
- Confusing retrieval confidence with permission to intervene.
- Deleting a UI row without removing its runtime effect.
- Reset that leaves indexes, caches, or audit state behind.
- Attractive UI over a fake or pre-scripted backend.
- Too many services for a personal SQLite-scale problem.
- RUN.md commands that were never tested from the submitted SHA.

---

## 20. Final review script

The finished submission should make this sequence effortless:

1. Clone exact SHA.
2. Copy `.env.example` to `.env` with no secret required.
3. Start the stack with one command.
4. Open the guided demo.
5. Teach `Aditya -> Aaditya` and `Kiwi -> Kivi` in Sarvam context.
6. Observe a correct intervention.
7. Observe abstention for `kiwi fruit`.
8. Inspect scores, reason codes, and source evidence.
9. Suppress or delete a memory and verify behavior changes.
10. Reset and reseed.
11. Import a new JSONL corpus.
12. Run the complete evaluation with one command.
13. Open the report and inspect a failure by case ID.
14. Confirm latency, storage, provenance, baselines, and ablations.

If these fourteen actions work from a clean clone, the submission directly answers almost every concern in the brief.

---

## 21. Definition of done

The project is done only when:

- its supported claim is written before the headline score;
- the product changes behavior using actual persisted state;
- learning, retrieval, intervention, and abstention are independently inspectable;
- every applied edit has provenance;
- ambiguous and ordinary-word negatives are first-class evaluation cases;
- memory can be controlled without database access;
- failures remain visible in committed results;
- the frozen test has not been used for threshold tuning;
- the exact submitted commit passes tests and evaluation;
- the exact documented startup, import, inspection, reset, and evaluation procedures work from a clean clone;
- README discloses all AI assistance and honestly states limitations.

No plan can guarantee selection. This plan maximizes the signals the assignment appears designed to measure: judgment, trustworthy backend behavior, rigorous evaluation, clear product thinking, and operational completeness.

---

## Technical references

- FastAPI testing and TestClient: https://fastapi.tiangolo.com/tutorial/testing/
- FastAPI features and OpenAPI support: https://fastapi.tiangolo.com/features/
- Alembic migrations: https://alembic.sqlalchemy.org/en/latest/index.html
- SQLite FTS5: https://www.sqlite.org/fts5.html
- RapidFuzz similarity functions: https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html
- Jellyfish phonetic and approximate matching: https://github.com/jamesturk/jellyfish
- pytest parametrization: https://docs.pytest.org/en/stable/how-to/parametrize.html
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
