# Reference Implementation (Golden Path)

This is the copy/paste integration package for Limiq.io.

## Commands
```bash
cd examples/reference-implementation
make up
make demo-allow
make demo-deny
```

## Expected console output
From demo commands you should see:
- `✅ capability issued`
- `✅ verify = ALLOW`
- `✅ action executed`
- `✅ verify = DENY (reason=SPEND_LIMIT_EXCEEDED)`

## Services
- `postgres`
- `redis`
- `api`
- `purchase-target`
- `agent-demo` (one-shot runner)

## Ports
- API: `http://localhost:8000`
- Purchase target: `http://localhost:3002`
