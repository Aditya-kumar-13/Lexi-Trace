# V7 phase 4 adversarial discovery

Status: round 1 complete; no second round authorized by the frozen stopping rule.

Round 1 used the maximum 40 cases and targeted five predeclared failure classes:

- eight provider-confidence abuse cases in unrelated contextual uses;
- eight Unicode and emoji offset cases;
- eight same-span collisions with reversed memory insertion order;
- eight independent repeated-span cases;
- eight Hindi-English code-switched negative contexts.

LexiTrace produced 40/40 exact outputs and actions, 16/16 useful interventions, and zero wrong
automatic edits. The naive dictionary made 24 wrong automatic edits on the identical inputs, which
shows that the negative and collision cases were capable of exposing an unsafe replacement system.

No new failure was discovered, so there is no finding to fix, accept as residual risk, or promote
into the adversarial regression corpus. The frozen Definition of Done allows another exploratory
round only when the preceding round reveals a new high-severity failure class. Round 2 is therefore
not run. This is a stopping-rule decision, not a claim that further testing could never find a bug.

Dataset hash and complete case-level results are committed. The final holdout was not accessed.
