# V7 phase 5 operational verification

Status: complete for the backend assignment. Optional external certification remains unclaimed.

The reviewer demo now exercises the complete visible contract in one local process with no network
or API key: teach Kivi, apply it in service context, abstain in fruit context, record typed feedback,
inspect and export memory, keep two different Aditya memories ambiguous, and reset all state. The
two-Adityas case returns the original text, a suggestion, and both candidates rather than choosing
by ordering.

The cross-platform gate now replays v7 calibration, includes adversarial regression, runs the demo,
and preserves the usual backend, migration, baseline, soak, and frontend checks. The final local
verification produced:

- 50/50 backend tests passed;
- Ruff format and lint passed;
- Alembic reported no pending migration operations;
- the frozen v6 baseline hash verification passed;
- the Vite production build completed successfully;
- submission preflight passed every integrity, calibration, regression, credential, and version
  check;
- the reviewer demo completed with zero HTTP errors.

No final-holdout content was accessed. Its seal remains `awaiting_independent_custodian`; this is
an optional future external-certification tier rather than an incomplete assignment requirement,
and is relevant only if a final untouched external-evidence claim is pursued.
