# V7 phase 3 calibration candidate 3 review

Status: rejected by exact engine replay; not an active policy.

Candidate 3 restored a nonzero phonetic contribution. The directly affected unseen-variant test and
the smoke evaluation passed again, and offline calibration reported 71/72 exact outputs with zero
wrong automatic edits.

Exact engine replay then exposed a quantization boundary. Candidate traces store component signals
to four decimals. The offline replay placed a cold-route candidate fractionally below the selected
`0.89` apply threshold; the engine's full-precision arithmetic placed it exactly at `0.89`. Four
cold-route events therefore applied incorrectly in the lifecycle calibration journey.

Candidate 4 adds a conservative calibration rule before rerunning: minimize eligible candidate
scores within 0.0025 of the apply threshold before optimizing accuracy. It also searches learned-ASR
weight 0.24 and apply threshold 0.90 so a learned recovery can retain measurable headroom while a
cold route remains below threshold. All earlier candidate artifacts remain preserved.

The final holdout was not accessed.
