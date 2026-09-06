# Running LexiTrace

**Primary review method: native local Windows application using Python 3.12, Node.js 20 or newer,
and embedded SQLite. No API key or hosted service is required.**

The commands below are PowerShell commands run from the repository root unless a step says
otherwise. The local embedding model downloads once on first semantic use and is cached under
`data/models`.

## Required runtimes

- Python 3.12
- Node.js 20 or newer with npm

## Environment variables

No environment variable is required for the primary path. Defaults are built in and documented in
`.env.example`.

| Variable | Purpose | Default |
|---|---|---|
| `LEXITRACE_DATABASE_URL` | SQLite connection | `sqlite:///./data/lexitrace.db` |
| `LEXITRACE_CORS_ORIGINS` | Browser origins | local Vite origins |
| `LEXITRACE_SEMANTIC_ENABLED` | Enable local context embeddings | `true` |
| `LEXITRACE_SEMANTIC_MODEL` | FastEmbed model | `BAAI/bge-small-en-v1.5` |
| `LEXITRACE_SEMANTIC_CACHE_DIR` | Local model cache | `./data/models` |
| `LEXITRACE_SEMANTIC_THREADS` | Local ONNX worker threads | `1` |
| `LEXITRACE_MAX_REQUEST_BYTES` | Declared HTTP payload limit | `65536` |
| `LEXITRACE_POLICY_PATH` | Optional versioned policy override | unset |
| `VITE_API_BASE_URL` | Browser API base URL | `http://localhost:8000` |

## Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev,semantic]"
Push-Location apps/web
npm ci
Pop-Location
```

## Create, migrate, and seed the database

```powershell
New-Item -ItemType Directory -Force data | Out-Null
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/seed.py
```

## Start the application

Start the API in the first terminal:

```powershell
.\.venv\Scripts\python.exe -m uvicorn lexitrace.main:app --app-dir apps/api --host 127.0.0.1 --port 8000
```

Start the interface in a second terminal:

```powershell
Set-Location apps/web
npm run dev -- --host 127.0.0.1
```

Open http://localhost:5173. API documentation and direct inspection endpoints are available at
http://localhost:8000/docs.

## Primary interactions

1. Teach `Kiwi -> Kivi` with learned-context scope and the observation
   `Review the Kiwi service dashboard.`
2. Run `Inspect the Kiwi platform deployment.` The output should use `Kivi` even though it shares
   no literal learned context words. Inspect the semantic and sparse evidence in the result.
3. Run `Buy kiwi fruit from the shop.` The output should remain unchanged and expose its blocker.
4. Teach `Aditya -> Aaditya` with global scope and try it without special context.
5. Open the memory detail, evidence, and history views; reject or confirm an intervention.
6. Reset the demo and confirm that memories, observations, and traces disappear.

For a disposable reviewer demonstration that creates its own temporary database:

```powershell
.\.venv\Scripts\python.exe scripts/reviewer_demo.py
```

## Run the evaluations

Run the complete test, evaluation, calibration, soak, frontend-build, and submission gate with the
active virtual environment's Python. The runner is cross-platform and writes development artifacts
under `results/v7/development/current`, never into the frozen v6 result directories:

```text
python scripts/run_quality_gate.py
```

Use `python scripts/run_quality_gate.py --quick` for tests, formatting, lint, migrations, baseline
integrity, and submission checks without the longer behavioral suites.

Run the 28-case smoke suite against the complete hybrid product:

```powershell
.\.venv\Scripts\python.exe evaluation/run.py
```

Run the fixed 252-case robustness suite with predeclared calibration and held-out splits:

```powershell
.\.venv\Scripts\python.exe evaluation/run.py --dataset data/benchmark/robustness.jsonl --output results/robustness
```

Run chronological journeys against the hybrid product and semantic-disabled ablation:

```powershell
.\.venv\Scripts\python.exe evaluation/run_journeys.py
```

Run provider-aware ASR learning against the no-learning ablation:

```powershell
.\.venv\Scripts\python.exe evaluation/run_asr_learning.py
```

Run event-derived memory lifecycle journeys and the no-lifecycle ablation:

```powershell
.\.venv\Scripts\python.exe evaluation/run_lifecycle.py
```

Run conflict learning in both memory insertion orders:

```powershell
.\.venv\Scripts\python.exe evaluation/run_conflicts.py
```

Run the 500-decision local soak:

```powershell
.\.venv\Scripts\python.exe evaluation/run_soak.py
```

Freeze a threshold candidate from calibration data and run the safety release gate:

```powershell
.\.venv\Scripts\python.exe evaluation/calibrate_policy.py
```

The committed artifact rejects the `0.90` candidate and retains `0.93`; inspect its safety
violations before changing `policy.toml`. The interface can execute `0.90` as a shadow policy. Its
hypothetical output is persisted in the trace but never replaces the active result.

The first semantic run may download the declared local model. No transcript is sent to a hosted
inference API. Regenerate the fixed robustness corpus only when intentionally creating a new
dataset version:

```powershell
.\.venv\Scripts\python.exe evaluation/build_robustness_dataset.py
```

## Inspect results and state

- `results/latest`: smoke summary, report, and per-case JSONL
- `results/robustness`: robustness summary, visible failures, and per-case JSONL
- `results/journeys`: hybrid/ablation summary, report, and chronological cases
- `results/asr-learning`: learned-ASR/no-learning comparison and precision/coverage curve
- `results/lifecycle`: event-lifecycle/no-lifecycle comparison with per-event posterior evidence
- `results/calibration`: frozen threshold search, safety gate, and rollback boundaries
- `results/conflicts`: collision learning, multi-edit, and insertion-order evidence
- `results/soak`: sustained latency, trace uniqueness, failures, and database growth
- `data/lexitrace.db`: persistent SQLite memory state
- `GET /api/v1/memories`: current memory state
- `GET /api/v1/memories/{memory_id}/asr-evidence`: immutable provider-linked outcomes
- `GET /api/v1/decisions/{trace_id}`: persisted decision explanation
- `GET /api/v1/conflicts`: current surface and phonetic collision groups
- `GET /api/v1/metrics`: content-free request counters and mean route latency
- `GET /api/v1/users/{user_id}/export`: portable memory definitions
- `POST /api/v1/users/{user_id}/import`: merge or replace portable definitions
- `DELETE /api/v1/users/{user_id}`: complete user-state deletion

Every evaluated case retains the input, expected and actual behavior, relevant memory and
observation provenance, reason codes, blockers, database allocation, model calls, API cost, and
latency.

## Reset

Reset all product state while the API is running:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/reset
```

Or reset through the repository script while the API is stopped:

```powershell
.\.venv\Scripts\python.exe scripts/reset.py
```

To recreate the database from an empty file, stop the API and run:

```powershell
Remove-Item -LiteralPath data\lexitrace.db -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/seed.py
```

## Submission preflight

Run this before handing over a commit. It verifies required artifacts, result hashes, the migration
head, version agreement, corpus size, the documented review path, and common credential patterns.

```powershell
.\.venv\Scripts\python.exe scripts/verify_submission.py
```

## Optional Docker path

Docker Desktop with Docker Compose provides an alternative local path:

```powershell
docker compose up --build
docker compose exec api python scripts/seed.py
docker compose exec api python evaluation/run.py
```

Open http://localhost:5173. Generated results are bind-mounted into the repository `results`
directory. Reset user state through the interface or API. Remove the containerized database and
model cache with:

```powershell
docker compose down --volumes
```
