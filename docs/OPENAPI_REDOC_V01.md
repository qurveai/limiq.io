# Limiq.io — OpenAPI & ReDoc Guide (V01)

## URLs
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Playground & OpenAPI Types
`apps/playground` relies on OpenAPI-generated TypeScript types.

Commands:
- `pnpm --filter playground types:api` (from `openapi/openapi.snapshot.json`)
- `OPENAPI_SOURCE=url pnpm --filter playground types:api` (from live API)

Use this when API schemas change to keep playground requests/responses aligned.

## Authentication Header (MVP)
Routes sensibles utilisent:
- `X-Workspace-Id: <workspace_uuid>`

La valeur `workspace_id` du body/query doit matcher ce header, sinon `WORKSPACE_MISMATCH`.

Route de bootstrap workspace:
- `POST /workspaces` utilise `X-Bootstrap-Token: <bootstrap_token>`
- si `KYA_WORKSPACE_BOOTSTRAP_TOKEN` n'est pas configure cote serveur: `503 WORKSPACE_BOOTSTRAP_DISABLED`

## Error Contract
Toutes les erreurs metier suivent:

```json
{
  "detail": {
    "code": "SOME_CODE",
    "message": "Human readable message"
  }
}
```

## Main Endpoint Groups
- `health`: liveness/readiness
- `workspaces`: bootstrap create/get workspace
- `agents`: create/get/revoke
- `policies`: create/bind
- `capabilities`: token issuance
- `verify`: allow/deny decision engine
- `audit`: list/export/integrity

## Workspace Endpoint Contract
- `POST /workspaces`
  - Body: `name` (required), `slug` (optional)
  - Success: `201` with `id,name,slug,status,created_at`
  - Errors: `401 AUTH_BOOTSTRAP_MISSING|AUTH_BOOTSTRAP_INVALID`, `409 WORKSPACE_SLUG_ALREADY_EXISTS`, `503 WORKSPACE_BOOTSTRAP_DISABLED`
- `GET /workspaces/{workspace_id}`
  - Requires `X-Workspace-Id` equal to `{workspace_id}`
  - Errors: `403 WORKSPACE_MISMATCH`, `404 WORKSPACE_NOT_FOUND`

## Verify Decision Contract
`POST /verify` retourne:
- `decision`: `ALLOW` ou `DENY`
- `reason_code`: `null` si `ALLOW`, sinon code metier
- `audit_event_id`: event de decision dans l'audit

## Audit Integrity Contract
`GET /audit/integrity/check` retourne:
- `status`:
  - `OK`: chaine valide
  - `BROKEN`: divergence detectee
  - `PARTIAL`: fenetre partielle / preuve incomplète

## Open Source Doc Quality Checklist
- Chaque endpoint expose `summary` + `description`.
- Les erreurs 401/403/422 sont documentees uniformement.
- Les endpoints metier critiques documentent aussi 404/409/422 quand applicable.
- Les schemas incluent descriptions de champs sensibles (`workspace_id`, `public_key`, `capability_token`, etc.).
