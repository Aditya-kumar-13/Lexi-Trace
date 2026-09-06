# V7 semantic safety and lifecycle interaction

Status: exploratory development evidence; no production policy change.

## Question

The first multimodal experiment showed that stored-example retrieval recovered positive contexts
that a centroid diluted. It did not test whether either representation remained safe after
context-specific rejections or when two memories shared the same surface form. This experiment
adds both conditions and separately tests the current automatic lifecycle transition.

## Protocol

The fixed development file contains two chronological journeys. The first teaches three positive
Kivi contexts, records three rejected fruit-context interventions, and then scores four unseen
negative paraphrases plus three valid positive paraphrases. The second teaches two competing
memories for the surface `Kiwi` and scores four resolvable contexts plus two deliberately ambiguous
contexts.

The three rejected interventions are learning events, not scored examples. They remain in the case
artifact with `score_case: false`, so their traces and state effects are auditable without inflating
or depressing the reported metrics. Thirteen later inference events are scored. Every retrieval
mode is run with the automatic lifecycle both enabled and disabled; all other policy settings stay
fixed.

## Results

| Retrieval | Automatic lifecycle | Exact output | Action accuracy | Wrong interventions |
|---|---:|---:|---:|---:|
| Centroid | enabled | 9/13 (69.23%) | 9/13 (69.23%) | 1 |
| Nearest example | enabled | 9/13 (69.23%) | 9/13 (69.23%) | 1 |
| Centroid | disabled | 11/13 (84.62%) | 11/13 (84.62%) | 1 |
| Nearest example | disabled | 12/13 (92.31%) | 12/13 (92.31%) | 1 |

The sparse ablation makes no wrong intervention but reaches only 8/13 exact outputs and 4/13
correct actions. It is conservative because it misses useful applications and does not reproduce
the requested abstention semantics.

## Findings

1. Three context-specific rejections demote the confirmed Kivi memory to candidate under the
   current lifecycle. That prevents all three later valid Kivi corrections. Negative evidence is
   already blocking the four tested fruit contexts; changing global authorization state is an
   additional, harmful effect in this chronology.
2. Holding authorization fixed separates that lifecycle effect from retrieval. Nearest-example
   retrieval then preserves all seven positive applications and all four learned negative
   abstentions in this dataset.
3. Neither representation is safe enough to promote. Centroid incorrectly resolves one ambiguous
   collision to Kivi; nearest-example incorrectly resolves another to Kiwi Farms. In both cases a
   weak positive context signal just above the current 0.15 conflict floor is enough to authorize
   an edit.
4. This is discovery evidence, not a benchmark claim. The next experiment must sweep a
   predeclared conflict-context floor on development data, use zero wrong interventions as the
   primary constraint, and then recheck the selected structural combination across the broader
   regression suites before any calibration or default change.

## Reproduction

Run `evaluation/run_journeys.py` against
`data/benchmark/v7_semantic_safety_development.jsonl`. Select `centroid` or `nearest_example` with
`--semantic-retrieval-mode`; add `--disable-auto-lifecycle` for the fixed-authorization ablation.
The committed artifacts preserve the dataset hash, configuration, per-case traces, memory state,
and database accounting for all four runs.
