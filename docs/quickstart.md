# Quickstart (5 Minutes)

Goal: run the KYA reference integration and see one ALLOW + one DENY decision.

## 1) Start services
```bash
cd examples/reference-implementation
make up
```

## 2) Run ALLOW demo
```bash
make demo-allow
```
Expected lines:
- `✅ capability issued`
- `✅ verify = ALLOW`
- `✅ action executed`

## 3) Run DENY demo
```bash
make demo-deny
```
Expected line:
- `✅ verify = DENY (reason=SPEND_LIMIT_EXCEEDED)`

## If you hit errors
- `connection refused`:
  services are not up yet, rerun `make up` and wait 10-20s.
- `WORKSPACE_BOOTSTRAP_DISABLED`:
  API did not receive bootstrap token config.
- `SIGNATURE_INVALID`:
  request payload/signature mismatch.
- `POLICY_NOT_BOUND`:
  setup flow was interrupted before policy bind.

You can inspect running services with:
```bash
docker compose ps
```
