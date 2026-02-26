# Example — Express Target (Runnable)

Simple target service that verifies actions with Limiq.io before executing business logic.

## Prerequisites
- Limiq.io API running on `http://localhost:8000`
- SDK built once:
```bash
pnpm --filter @limiq/sdk-js build
```

## Run
```bash
cd examples/express-target
cp .env.example .env
npm install
set -a; source .env; set +a
npm run dev
```

Server starts on `http://localhost:3001`.

## Endpoints
- `GET /health`
- `POST /purchase`

`POST /purchase` expects the same payload as `POST /verify`.
If Limiq.io returns `DENY`, target returns `403` with `reason_code`.
