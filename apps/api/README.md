# Limiq.io API

## Quickstart
1. `cp .env.example .env`
2. `python3 -m venv .venv && source .venv/bin/activate`
3. `pip install -r requirements-dev.txt`
4. `docker compose up -d` (run from repo root)
5. `alembic upgrade head`
6. `uvicorn app.main:app --reload`

Health endpoint: `GET /health`
