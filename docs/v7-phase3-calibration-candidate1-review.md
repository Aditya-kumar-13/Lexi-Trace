# V7 phase 3 calibration candidate 1 review

Status: rejected after methodological review; not an active policy.

Candidate 1 searched all 23,328 predeclared combinations on 72 calibration events. It improved
the replayed v6 formula from 65/72 to 71/72 exact outputs, reduced wrong automatic edits from five
to zero, and reduced upper-clamped candidate scores from 44/74 to 0/74. The separately evaluated
safety corpus remained 16/16 with no wrong automatic edit.

The replay itself is valid: its v6 constants reproduce the engine's aggregate calibration results
exactly. The candidate is still rejected because the final stable JSON tie-break selected
`negative_context_weight = 1.0` even though every outcome tied at both searched negative weights.
In this corpus, the negative-evidence blocker dominates action selection, so the weight is not
identifiable. A lexical serialization order is not a scientific justification for a policy
constant.

Candidate 2 keeps the same corpus, search space, primary objective, and safety protocol. Its only
methodological change is declared before rerunning: after all behavioral and clamp criteria tie,
prefer values nearest the v6 baseline for constants that the data did not distinguish. Candidate 1
and its complete search results remain committed as the rejected audit record.

The final holdout was not accessed.
