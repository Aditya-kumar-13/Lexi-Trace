# Policy v7 Indic phonetic experiment

This is structural development evidence. It does not select or deploy a new live policy.

## Dataset

The committed corpus contains 48 labeled Romanized-name pairs: 24 intended-equivalent spellings and
24 deliberately similar but distinct names. It covers vowel length, aspiration, consonant doubling,
`sh/s`, `ksh/x`, and schwa-position variation. The corpus is known development data and may not be
used as v7 final-holdout evidence.

## Metaphone baseline

Metaphone equality produced:

- true positives: 10;
- false positives: 4;
- false negatives: 14;
- true negatives: 20;
- precision: 71.43%;
- recall: 41.67%.

This confirms that the current English-oriented hash is a poor fit for the targeted Romanization
patterns.

## Transparent graded experiment

The alternative normalizes a small declared set of Romanization choices and then measures graded
string similarity over the resulting skeleton. It does not claim to identify a language or convert
Devanagari. Every transformation is visible in `lexitrace/phonetics.py`.

The evaluator publishes every threshold from 0.70 through 0.99. It deliberately records no selected
threshold. At 0.91 through 0.99 the development corpus produces:

- true positives: 22;
- false positives: 0;
- false negatives: 2;
- true negatives: 24;
- precision: 100%;
- recall: 91.67%.

The two remaining false negatives are `Krishna/Krishan` and `Mohammad/Mohammed`. Adding rules merely
to make those known rows pass would be test-set fitting, so they remain visible failures.

## Next gate

This experiment is not ready for product use. It must be tested as a graded candidate-generation
feature against realistic transcript cases, collision attacks, short-token safeguards, and the
combined architecture. Only calibration data may select its live threshold and contribution.
