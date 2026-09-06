# Policy v7 baseline instrumentation

This is diagnostic development evidence, not final-holdout performance.

- Cases: **280**
- Retained candidates: **242**
- Scored candidates before cross-variant deduplication: **242**
- Cross-variant duplicates removed: **0**
- Retained duplicate-key violations: **0**
- Upper-clamped candidates: **142**
- Lower-clamped candidates: **0**

## Context controller

- none: **181**
- semantic: **48**
- sparse: **11**
- tie: **2**

## Contribution activity

- score_lexical_contribution: non-zero **242**, mean **0.6932**, mean absolute **0.6932**
- score_authorization_contribution: non-zero **229**, mean **0.1325**, mean absolute **0.1325**
- score_context_contribution: non-zero **199**, mean **0.0769**, mean absolute **0.0769**
- score_phonetic_contribution: non-zero **222**, mean **0.0917**, mean absolute **0.0917**
- score_asr_alternative_contribution: non-zero **12**, mean **0.0032**, mean absolute **0.0032**
- score_learned_asr_contribution: non-zero **0**, mean **0.0000**, mean absolute **0.0000**
- score_negative_context_contribution: non-zero **0**, mean **0.0000**, mean absolute **0.0000**

## Visible failures

| Case | Category | Expected | Actual | Expected action | Actual action |
|---|---|---|---|---|---|
| global-unseen-phonetic-01-00 | global-unseen-phonetic-positive | Message Aaditya before lunch. | Message Adithya before lunch. | apply | suggest |
| global-unseen-phonetic-01-01 | global-unseen-phonetic-positive | Ask Aaditya to open the file. | Ask Adithya to open the file. | apply | suggest |
| global-unseen-phonetic-01-02 | global-unseen-phonetic-positive | The Aaditya item is ready. | The Adithya item is ready. | apply | suggest |
| context-positive-01-02 | contextual-positive | Inspect the Postgres query logs. | Inspect the post grass query logs. | apply | suggest |
