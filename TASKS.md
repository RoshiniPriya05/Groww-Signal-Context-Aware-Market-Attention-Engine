# Groww Signal — initialization task list

Generated after scaffolding the attention-engine watchlist monorepo.

## Done

- [x] Monorepo layout: `backend/` (FastAPI) and `frontend/` (Next.js App Router)
- [x] `docker-compose.yml` with PostgreSQL **5432** and Redis **6379**, healthchecks, named volumes, and schema bootstrap
- [x] Backend deps in `backend/requirements.txt` and `backend/pyproject.toml`: fastapi, uvicorn, asyncpg, redis, pydantic, numpy, openai
- [x] `backend/schema.sql`: `users`, `watchlists`, `user_session_snapshots`, `signals`
- [x] FastAPI app: CORS, lifespan pool/Redis, `GET /health`, placeholder `GET /api/signals`
- [x] Next.js + TypeScript + Tailwind v4 + Lucide; forced dark theme using Groww mint (`#00d09c`) on near-black surfaces
- [x] Root `README.md`, `.gitignore`, `.env.example` files, connectivity script `backend/scripts/verify_connectivity.py`

## Blocked on this machine

- [ ] Start Docker Compose (`docker compose up -d`)
- [ ] Verify Postgres/Redis connectivity and that `schema.sql` tables exist

**Why:** `docker` is not on PATH, Docker Desktop is not installed, WSL has no distro, and ports **5432** / **6379** are closed. Installing Docker Desktop is a host-level change and was not applied.

**Unblock:** Install and start Docker Desktop (or another Compose runtime), then from the repo root:

```powershell
docker compose up -d
cd backend
py -3 -m pip install -r requirements.txt
py -3 scripts/verify_connectivity.py
```

Expect `postgres: ok` with the four tables and `redis: ok ping=True`. Then `uvicorn app.main:app --reload --port 8000` and `GET http://localhost:8000/health` should report both stores healthy.

## Initialized tree

```
groww/
  docker-compose.yml
  README.md
  TASKS.md
  backend/
    app/main.py, config.py, db.py
    schema.sql
    requirements.txt
    pyproject.toml
    scripts/verify_connectivity.py
  frontend/
    src/app/{layout,page,globals}.tsx/css
    package.json
```

## Suggested next work

- [ ] Wire watchlist CRUD against Postgres
- [ ] Cache latest quotes / RSI in Redis
- [ ] Compute `attention_score` into `signals`
- [ ] Replace sample frontend rows with `/api/signals`
