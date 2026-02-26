# Limiq.io Architecture (V01)

## Overview
Limiq.io provides an identity and permission layer for autonomous agents.

Core responsibilities:
- register agent identities
- attach policy constraints
- issue capability tokens
- verify signed actions
- maintain an auditable and integrity-checked event trail

## Main Components
- `agent_registry`: create/get/revoke agents
- `policy_service`: create policies and bind them to agents
- `capability_issuer`: issue short-lived capability JWTs
- `verify_engine`: evaluate action requests (ALLOW/DENY + reason)
- `audit_log`: append events, export logs, verify hash-chain integrity

## Data Stores
- PostgreSQL:
  - source of truth for agents, policies, capabilities, audit events
- Redis:
  - revocation cache and rate-limit counters

## Security Model (MVP)
- workspace context from `X-Workspace-Id`
- request `workspace_id` must match auth context
- Ed25519 signatures for action verification
- JWT capability tokens (EdDSA)

## Audit Integrity
- append-only events
- hash-chain with `prev_hash` and `event_hash`
- integrity check endpoint returns `OK`, `BROKEN`, or `PARTIAL`

## Request Flow (High Level)
1. Client registers agent
2. Client creates and binds policy
3. Client requests capability
4. Agent signs action envelope
5. Client calls `/verify`
6. System writes audit events
7. Consumers query/export/check integrity
