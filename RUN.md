# Running LexiTrace

**Primary review method: Local Docker Compose application with an embedded SQLite database. No
external model key is required.**

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
python -m pip install -e ".[dev]"
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

1. Teach `Kiwi -> Kivi` with contextual scope, positive context `Sarvam, service`, and negative
   context `fruit, food, shopping`.
2. Run `Review the Sarvam Kiwi service.` and inspect the applied decision.
3. Run `Buy kiwi fruit from the shop.` and inspect the abstention.
4. Teach `Aditya -> Aaditya` with global scope and try it without special context.
5. Reset the demo and confirm that all user memories and traces disappear.

The current benchmark is a 28-case north-star smoke suite. It intentionally includes contextual
negatives, lifecycle cases, collisions, multiple spans, Unicode, word-boundary traps, and unseen
fuzzy/phonetic variants. It is not the final claimed benchmark; the larger curated split and import
workflow remain in development.
