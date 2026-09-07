# Policy v7 definition of done

Status: frozen before implementation of any v7 scoring change.

Assignment scope note: the independently authored final holdout below is an optional external-
certification tier. The backend assignment requires complete, reproducible included evaluation but
does not provide or require a private benchmark. V7 may be submitted without making an external-
accuracy claim; the holdout rules remain binding if that separate claim is pursued later.

Policy v7 is a simplification and validation release, not a feature expansion. Its purpose is to
retain only the smallest set of signals that measurably improves safe personal-term correction.

## Product contract

The core flow remains `teach -> retrieve -> evaluate -> apply/suggest/abstain -> learn feedback`.
An automatic edit is permitted only when the candidate clears both the ranking threshold and every
eligibility gate. A suggestion may surface an unconfirmed or context-cold candidate so the user can
provide the evidence required for later promotion. Negative-context evidence may force abstention.

The score is a ranking value, not a probability and not the primary safety boundary. Eligibility
gates enforce invariants that must not be traded away for recall.

## Frozen data roles

The existing v6 datasets and results are development evidence for v7 because their cases and
outcomes are already known. They may not be presented as untouched v7 final evidence.

V7 uses four non-overlapping roles:

1. Structural development data selects signal representations and exposes interactions.
2. Calibration data selects transformations, weights, and thresholds after the structure freezes.
3. The safety gate contains fixed unacceptable automatic edits and has zero tolerance.
4. The final holdout is independently prepared, sealed by hash, and opened once only after v7 is
   frozen. It cannot influence selection, calibration, documentation changes, or stopping.

If the final holdout causes any implementation or policy change, it is consumed development
evidence. A new independently prepared holdout must be sealed before another final claim.

## Predeclared component-retention rule

A component remains in the default product only if it provides at least one of the following on
structural development data:

- changes the final action in at least 2% of applicable realistic cases while preserving safety;
- uniquely prevents at least one high-severity wrong automatic intervention;
- materially improves a predeclared failure class that no simpler component handles;
- provides an operational fallback whose measured reliability justifies its complexity.

Every decision also considers latency, storage, conceptual cost, implementation size, and overlap
with other signals. The 2% rule is not used to remove safety gates whose rare activation prevents a
high-severity failure.

The following alternatives must be compared on identical inputs before selection:

- double-counted versus single-path ASR confidence;
- centroid versus bounded stored-example semantic retrieval;
- Metaphone versus graded Indic-aware phonetic distance;
- exact-route ASR reliability versus hierarchical backoff versus removal;
- Boolean authorization versus continuous trust contribution;
- current versus any proposed conflict simplification.

Individual winners are provisional. The combined configuration must be re-instrumented on
structural development data to detect interaction effects before calibration begins.

## Correctness gates

V7 is complete only when:

- all unit, integration, migration, lint, formatting, and frontend-build checks pass;
- candidate generation produces at most one retained candidate per `(memory_id, start, end)`;
- two occurrences of one surface form are scored independently;
- exact overlapping ties never auto-apply by lexical ordering;
- global-memory collisions do not crash and remain deterministic under reversed insertion order;
- non-overlapping winners cannot corrupt character offsets;
- duplicate event IDs do not change trust or provider evidence;
- the fixed safety suite has zero wrong automatic interventions;
- every known adversarial regression has zero wrong automatic interventions;
- exploratory red-team findings are all fixed or recorded as accepted residual risk with rationale;
- the final frozen holdout is evaluated exactly once under its sealed hash.

Final-holdout reporting must include exact output, action accuracy, intervention precision, recall,
wrong interventions, latency, and every failure. No percentage may be reported without its numerator
and denominator.

## Evidence and calibration gates

Before calibration, the selected combined architecture must report:

- raw and deduplicated candidate counts by retrieval route;
- contribution of every score term before and after clamping;
- the fraction of candidates that hit either clamp boundary;
- raw sparse and semantic positive/negative distributions;
- the fraction of cases in which each context representation controls the combined signal;
- final-action changes attributable to each optional component;
- embedding calls, multi-candidate latency, and stored evidence growth.

Any scoring change introduced by a red-team fix returns to calibration and the independent safety
gate before promotion into the frozen adversarial regression suite. A pure eligibility blocker that
does not modify scores still reruns the complete safety and regression gates.

All selected constants must be stored in the versioned policy file and justified by an artifact.
Policy v7 must use a new version identifier. V6 results are never overwritten.

## Semantic-storage gate

If bounded stored-example retrieval wins, it must define before implementation:

- a fixed per-memory, per-polarity cap;
- model identifier and version on every vector;
- duplicate-context suppression;
- deterministic diversity-preserving retention and eviction;
- behavior when the active model differs from stored evidence;
- a measured storage-growth ceiling.

## Adversarial-testing contract

Exploratory red-team work is judged by the quality of discoveries and triage, not by a zero count.
Every finding records the input, mechanism, severity, resulting action, resolution, and regression
case or accepted-risk rationale. Fixed discoveries are promoted into an immutable adversarial
regression corpus where zero wrong automatic interventions is mandatory.

Exploration is bounded to two predeclared rounds of at most 40 cases each for this release. A new
round is allowed only when the previous round reveals a new high-severity failure class.

## Operational and reviewer gates

- One cross-platform command runs the complete quality and evaluation gate.
- A clean checkout can start, migrate, become healthy, reset, and evaluate without undocumented
  steps.
- The product starts without an API key.
- Lack of network access or a semantic-model cache causes documented sparse fallback, not a hang.
- A context-free reviewer follows the documented path without improvisation and reports every
  ambiguity as a defect.
- The illustrative demo is labeled as a walkthrough, not evaluation evidence, and includes a safe
  two-Adityas ambiguity case.

## Stop condition

V7 stops when the frozen structural comparisons are decided, the combined architecture is
re-instrumented, calibration and all gates pass, red-team work meets its bounded contract, the
reviewer cold read succeeds, and all remaining limitations are documented.

The final holdout is never consulted to decide whether to stop. New alternatives are not added after
structural selection freezes unless a high-severity development or red-team finding demonstrates a
failure class that the selected architecture cannot address.
