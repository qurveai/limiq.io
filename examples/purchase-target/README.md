# Example — Purchase Target (Integration Proof)

Reference integration that protects a real business action (`POST /purchase`) with Limiq.io verify.

## Goal
Show a complete ALLOW + DENY flow in a few minutes:
1. Bootstrap workspace/agent/policy/capability via Limiq.io API.
2. Sign purchase actions.
3. Call target endpoint.
4. Target verifies with Limiq.io before execution.

## Prerequisites
- Limiq.io API running on `http://localhost:8000`
- `KYA_WORKSPACE_BOOTSTRAP_TOKEN` configured in API env
- SDK JS built once:

```bash
pnpm --filter @limiq/sdk-js build
```

## Run target service
```bash
cd examples/purchase-target
cp .env.example .env
npm install
set -a; source .env; set +a
npm run dev
```

Server runs on `http://localhost:3002`.

## Run demo (API-first setup)
In another terminal:

```bash
cd examples/purchase-target
set -a; source .env; set +a
npm run demo
```

Expected output includes:
- `OK Workspace created`
- `OK Agent created`
- `OK Policy created`
- `OK Policy bound`
- `OK Capability issued`
- `OK ALLOW verified and purchase executed`
- `OK DENY verified and purchase blocked (SPEND_LIMIT_EXCEEDED)`

## Endpoints
- `GET /health`
- `POST /purchase`

`POST /purchase` expects the same body shape as `POST /verify`.
If Limiq.io returns `DENY`, target returns `403` with `reason_code`.
