# V7 phase 3 calibration candidate 2 review

Status: rejected by the frozen regression gate; not an active policy.

Candidate 2 corrected Candidate 1's unidentifiable negative-context tie and passed the independent
16-case safety gate with zero wrong automatic edits. It achieved 71/72 exact calibration outputs,
zero wrong automatic edits, and zero upper-clamped scores.

Promotion was still rejected. Its selected `phonetic_weight = 0.0` contradicted Phase 2's frozen
decision to retain the phonetic route. The engine-level gate demonstrated the consequence:

- unseen `Aditiya -> Aaditya` recovery stopped applying;
- the smoke suite fell below its frozen regression floor at 25/28;
- the shadow-policy API test no longer exercised its documented threshold crossover.

Candidate 3 therefore restarts calibration with a structural constraint declared before its search:
the retained phonetic component must have a nonzero contribution, so the searched values are 0.05
and 0.10. All other corpus hashes, candidates, primary objectives, and post-selection safety rules
remain unchanged. Candidate 2's search and failures remain preserved as evidence.

The final holdout was not accessed.
