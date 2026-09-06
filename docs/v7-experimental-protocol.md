# Policy v7 experimental protocol

This protocol is frozen with the v7 Definition of Done before scoring implementation changes.

## 1. Baseline preservation

The v6 baseline is commit `ca9cbe7` with policy
`2026-09-06-hybrid-v6-conflict-safe`. A machine-readable manifest records SHA-256 hashes for the
policy, benchmark inputs, and committed result artifacts. Verification must fail if any frozen v6
artifact changes.

V6 traces are immutable JSON evidence. Current v7 application code is not required to deserialize
them. Any v6 comparison requiring execution must run the frozen v6 commit in a separate checkout.

## 2. Dataset partition rules

| Partition | May select structure | May tune constants | Hard release gate | Final reporting |
|---|---:|---:|---:|---:|
| Existing v6 corpora | Yes | No | Regression only | Historical comparison |
| V7 structural development | Yes | No | No | Diagnostic |
| V7 calibration | No | Yes | No | Diagnostic |
| V7 safety | No | No | Yes | Yes |
| V7 adversarial discovery | Yes | No | No | Triage only |
| V7 adversarial regression | No | No | Yes | Yes |
| V7 final holdout | No | No | One-time | Yes |

No case may move from development or calibration into the final holdout. An adversarial discovery
may be copied into the adversarial regression set only after its resolution is decided; it never
becomes final-holdout evidence.

## 3. Holdout lifecycle

The final-holdout content is prepared by an independent custodian and kept outside the development
working tree. Before structural selection, the repository records:

- SHA-256 hash;
- non-empty case count;
- opaque dataset identifier;
- custodian identifier;
- UTC sealing timestamp.

Development receives only this seal. The holdout guard verifies the supplied file against the seal
and refuses a second recorded opening. The opening receipt records the policy version, Git commit,
dataset hash, command, UTC time, and output location.

Repository tooling cannot prevent a person from bypassing source code, so the independent
custodian remains part of the control. The guard makes compliant use mechanically visible and
auditable.

If results trigger a change, the receipt marks the holdout consumed. Those cases become development
evidence and cannot support another final claim.

## 4. Structural experiments

Each alternative is implemented behind an evaluation-only selector. Both systems receive identical
memories, events, candidates, and inputs. Experiments record:

- exact output and action;
- wrong automatic interventions;
- intervention precision and recall;
- per-case action changes;
- score contributions and blockers;
- latency, model calls, and allocated storage;
- cases uniquely fixed and uniquely broken.

Candidate instrumentation records counts before and after both deduplication layers. The invariant
is one retained candidate per `(memory_id, start, end)`; different occurrences remain separate
because their spans differ.

No structural alternative is chosen from calibration, safety, or final-holdout performance.

## 5. Combined-configuration check

After provisional component selection, the full combination runs again on structural development
data. Its distributions are compared with every isolated experiment to detect interaction effects,
including clamp saturation and loss of marginal headroom. Any changed conclusion is resolved before
the architecture freezes.

## 6. Calibration

Only after architecture freeze may calibration data select normalization, transformations, weights,
and thresholds. Searches record the full search space, input hashes, every candidate result, the
selection rule, and rejected candidates.

The safety corpus is then evaluated without further selection. A candidate causing any additional
wrong automatic intervention is rejected. Any subsequent scoring modification invalidates the
calibration artifact and restarts this section under a new candidate policy version.

## 7. Adversarial workflow

Exploratory rounds target threshold boundaries, near-tie collisions, negative-evidence poisoning,
provider-confidence abuse, duplicate-event replay, overlapping spans, Unicode boundaries, and
code-switched contexts. Findings are successful discoveries, not failed exploration.

For each finding:

1. Assign severity and reproduce it.
2. Choose fix or accepted residual risk.
3. If scoring changes, return to calibration and safety evaluation.
4. If only eligibility changes, rerun every safety and regression gate.
5. Promote the case into the frozen adversarial regression corpus.

## 8. Demo and documentation

The demo is an illustrative operational contract, never a metric. It must show teaching, safe
application, contextual abstention, feedback, inspection, reset, and ambiguity between two people
whose observed name is `Aditya`. Its cases are excluded from final-holdout statistics.

Reports expose every failure and label small behavioral suites with counts rather than statistically
meaningless percentage headlines.

## 9. Final evaluation

After code, policy, documentation, and calibration freeze:

1. Record the candidate Git commit and policy version.
2. Verify the external holdout against its committed seal.
3. Run the complete gate once.
4. Write the opening receipt before inspecting case-level results.
5. Publish complete results, including every failure.

If the result is accepted without changes, it becomes the v7 final artifact. If anything changes,
mark it consumed and repeat the process only with a newly sealed independent holdout.
