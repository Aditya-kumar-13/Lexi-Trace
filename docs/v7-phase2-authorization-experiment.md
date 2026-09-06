# V7 authorization score experiment

Status: Boolean authorization retained; no production behavior changed.

## Question

Memory state already acts as a hard eligibility gate: an unconfirmed memory cannot auto-apply. The
score also contains a Boolean authorization contribution. This experiment asks whether replacing
that contribution with the memory's beta-posterior trust would add useful calibration or merely
count the same evidence twice.

Both modes keep the state blocker unchanged. In posterior mode, an unauthorized memory receives
zero authorization contribution; only an already-confirmed memory uses its posterior. An initial
implementation incorrectly gave candidate memories nonzero authorization credit. That invalid
version was discarded before evidence was preserved.

## Results

| Suite and mode | Exact output | Action accuracy | Wrong interventions |
|---|---:|---:|---:|
| Robustness, Boolean | 248/252 | 248/252 | 0 |
| Robustness, posterior | 239/252 | 239/252 | 0 |
| Semantic safety, Boolean | 13/13 | 13/13 | 0 |
| Semantic safety, posterior | 12/13 | 12/13 | 0 |

Across the 219 robustness candidates, Boolean authorization produces 128 raw scores above 1.0;
posterior authorization reduces that count to 119 and lowers mean clamped score from 0.9672 to
0.9583. The nine fewer clamps correspond to nine useful interventions lost at the active 0.93
threshold. No wrong intervention is removed because both modes already have zero.

## Decision

Retain Boolean authorization. Confirmation is an eligibility fact, not a confidence estimate, and
the posterior is already used to decide lifecycle state. Reusing it inside the score weakens valid
confirmed memories and double-counts lifecycle evidence without improving safety.

Score saturation remains real, but this experiment shows that authorization is the wrong lever for
fixing it. Saturation should be addressed when the score composition and context transformation are
recalibrated after structural selection. `authorization_score_mode` remains an internal evaluation
parameter with `boolean` as its default.

The robustness file's historical `heldout` partition was already consumed under v6 and is not the
sealed v7 final holdout.
