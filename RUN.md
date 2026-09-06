# Running LexiTrace

**Primary review method: Local Docker Compose application with an embedded SQLite database. No
external model key is required. The local embedding model downloads once on first semantic use.**

## Docker

Requirements: Docker Desktop with Docker Compose.

```powershell
docker compose up --build
```

Open http://localhost:5173. API documentation is at http://localhost:8000/docs.

Reset the demo user from the interface, or run:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/reset
```

Stop the application:

```powershell
docker compose down
```

Remove the local Docker database and return to a completely empty installation:

```powershell
docker compose down --volumes
```

## Native development

Requirements: Python 3.12 and Node.js 20 or newer.

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,semantic]"
alembic upgrade head
uvicorn lexitrace.main:app --app-dir apps/api --reload
```

Frontend, in a second terminal:

```powershell
cd apps/web
npm install
npm run dev
```

Run backend tests:

```powershell
python -m pytest
```

Run the reproducible north-star benchmark:

```powershell
python evaluation/run.py
```

Run chronological semantic and ASR journeys, including the sparse ablation:

```powershell
python evaluation/run_journeys.py
```

Backfill semantic vectors for usable observations created before migration `0004`:

```powershell
python scripts/backfill_semantic.py
```

Inspect `results/latest/report.md`, `results/latest/summary.json`, and
`results/latest/cases.jsonl`. Every LexiTrace result includes its persisted trace ID and candidate
details.

Seed demonstration memories:

```powershell
python scripts/seed.py
```

Reset all native local data:

```powershell
python scripts/reset.py
```

## Primary interactions

1. Teach `Kiwi -> Kivi` with learned-context scope and the example
   `Review the Kiwi service dashboard.`
2. Run `Inspect the Kiwi platform deployment.` and inspect the semantic evidence. This sentence
   deliberately shares no learned context keywords.
3. Run `Buy kiwi fruit from the shop.` and inspect the explicit context blocker.
4. Teach `Aditya -> Aaditya` with global scope and try it without special context.
5. Reset the demo and confirm that all user memories and traces disappear.

The 28-case smoke suite covers deterministic safety and lifecycle behavior. The chronological
journey suite separately measures semantic generalization, negative-prototype recovery, ASR N-best
recovery, and the sparse-context ablation. Both are development benchmarks rather than external
claims of production accuracy.
