# @limiq/sdk-js (WIP)

JavaScript SDK for Limiq.io.

## Scope (MVP)
- deterministic canonical JSON for verify envelope
- Ed25519 key generation (base64)
- signature generation on SHA-256 digest
- helpers to build `POST /verify` payload
- lightweight client for `/capabilities/request` and `/verify`

## Install (workspace)
```bash
pnpm --filter @limiq/sdk-js test
pnpm --filter @limiq/sdk-js build
```

## Usage
```ts
import {
  LimiqClient,
  buildSignedRequest,
  generateKeys,
} from "@limiq/sdk-js"

const keys = generateKeys()

const capabilityToken = "<capability_jwt>"
const verifyPayload = buildSignedRequest({
  workspace_id: "<workspace_uuid>",
  agent_id: "<agent_uuid>",
  action_type: "purchase",
  target_service: "stripe_proxy",
  payload: { amount: 18, currency: "EUR", tool: "purchase" },
  capability_token: capabilityToken,
  privateKeyBase64: keys.privateKeyBase64,
})

const client = new LimiqClient({
  baseUrl: "http://localhost:8000",
  workspaceId: "<workspace_uuid>",
})

const decision = await client.verifyAction(verifyPayload)
console.log(decision.decision, decision.reason_code)
```

## Encodings
- public key: base64 standard (32 bytes)
- private key: base64 standard (64 bytes)
- signature: base64 standard (64 bytes)

These encodings are aligned with backend validation (`base64.b64decode(..., validate=True)`).
