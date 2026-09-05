# Groww Signal

Attention-engine stock watchlist. Surfaces the few names that deserve a look, instead of dumping every tick.

## Stack

- **Backend:** FastAPI + Uvicorn (`backend/`)
- **Frontend:** Next.js, TypeScript, Tailwind CSS, Lucide (`frontend/`)
- **Data:** PostgreSQL + Redis via Docker Compose

## Local setup

Docker Desktop (or another Compose runtime) must be installed and running. Then:

```bash
docker compose up -d
```

Wait until both services are healthy, then:

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend
npm install
npm run dev
```

- API: http://localhost:8000/health
- UI: http://localhost:3000
