# V7 typed feedback experiment

Status: evaluation candidate; legacy behavior remains the product default.

## Problem

The old lifecycle treated every rejected intervention as evidence that the spelling memory itself
was false. That is appropriate when a global identity mapping is contradicted, but not when a
contextual memory sees a legitimate exception. A rejected `kiwi` fruit edit should teach a negative
context; it should not erase confidence that `Kiwi` means `Kivi` in the user's product contexts.

## Candidate design

Decision feedback now accepts an auditable scope:

- `context` stores sparse and semantic negative context evidence but does not lower identity trust;
- `identity` stores the same negative evidence and contributes to lifecycle demotion;
- `auto` resolves an incorrect global-memory intervention as identity feedback and an incorrect
  contextual-memory intervention as context feedback;
- `legacy` preserves the previous behavior and remains the API default during evaluation.

Correct feedback is recorded as confirmation regardless of the supplied scope. Explicit memory
suppression remains authoritative. The distinction is persisted in the existing observation reason
code, so no destructive data rewrite is needed. Replayed feedback is idempotent, and legacy
`USER_REJECTED` observations remain valid and count as identity evidence.

The trust profile reports identity-negative and contextual-negative events separately. Contextual
negative weight is visible for audit but is not added to the beta posterior that authorizes the
identity mapping.

## Results

| Evaluation | Result | Wrong interventions |
|---|---:|---:|
| Existing lifecycle suite, scope-aware `auto` | 16/16 events | 0 |
| No-lifecycle ablation in the same run | 14/16 events | 0 |
| Semantic safety chronology, scope-aware `auto` | 13/13 queries | 0 |

The semantic run also uses nearest-example retrieval and the 0.20 development conflict floor. It
keeps automatic lifecycle enabled, proving that the earlier 13/13 result no longer depends on
globally disabling state transitions.

Focused API tests additionally verify that an explicit context rejection keeps a contextual memory
confirmed, repeated feedback has zero additional influence, and an explicit identity rejection can
still demote that same memory.

## Limits and next gate

The `auto` rule is intentionally transparent, but memory scope is still a coarse proxy for user
intent. Before promotion it needs adversarial journeys in which a contextual memory's identity is
actually wrong and a global memory has a legitimate exception. Those cases must show that the
explicit `identity` and `context` controls recover the correct behavior and that the UI can present
the distinction without requiring technical vocabulary.

No active scoring constant, retrieval default, lifecycle default, or policy version changed in this
experiment.
