# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-02-26

### Added

- OSS governance baseline: `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- Workspace bootstrap endpoint (`POST /workspaces`) with `X-Bootstrap-Token` auth and `GET /workspaces/{id}`.
- Internal playground (`apps/playground`): workspace management, dev signing helpers, API explorer.
- SDK JS (`@kya/sdk-js`): `canonicalize`, `generateKeys`, `signAction`, `buildSignedRequest`, `KyaClient`.
- SDK Python (`kya-sdk`): `canonicalize`, `generate_keys`, `sign_action`, `build_signed_request`, `KyaClient`, `AsyncKyaClient`.
- Shared cross-language verify test vectors (`shared-test-vectors/verify/`), including non-ASCII key coverage.
- Runnable integration examples: `examples/express-target`, `examples/fastapi-target`.
- Reference integration example `examples/purchase-target` with full ALLOW/DENY demo script (`agent-demo.js`).
- Examples health smoke script (`scripts/examples_smoke.sh`) and CI job.
- Business smoke script (`scripts/examples_purchase_smoke.sh`) and CI job with live API.
- `scripts/verify_all.sh` + `make verify-all` for single-command full stack verification.
- Request logging middleware: every HTTP request logged with `method`, `path`, `status`, `latency_ms`.
- Runtime config: `LOG_LEVEL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE_SECONDS`, `RATE_LIMIT_REDIS_FAIL_OPEN`.
- Policy JSON strict schema validation (`extra="forbid"`) — returns `422 POLICY_SCHEMA_INVALID` on unknown/mistyped fields.
- Alembic migration `0003`: indexes on `capabilities(agent_id, status)`, `agents(fingerprint)`, `revocations(jti)`.

### Changed

- Canonical key ordering hardened to pure lexicographic sort (`<`/`>`, not `localeCompare`).
- CI expanded with dedicated `sdk_js`, `sdk_python`, `examples_smoke`, and `examples_purchase_smoke` jobs.
- Exception handling on critical paths (Ed25519 verify, JWT decode, Redis) replaced with explicit types and structured `warning`/`error` logs.
- Redis rate-limit failure mode configurable: fail-closed (default) or fail-open via `RATE_LIMIT_REDIS_FAIL_OPEN=true`.

### Fixed

- `POST /policies` now rejects malformed `policy_json` (typos in field names silently ignored previously).

## [0.5.0] - 2026-02-25

### Added

- MVP backend capabilities including:
  - agent registry
  - policy binding
  - capability issuance
  - verification engine
  - audit exports
  - audit integrity check
  - OpenAPI/ReDoc documentation
