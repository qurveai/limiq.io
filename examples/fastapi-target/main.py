import os

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class VerifyPayload(BaseModel):
    workspace_id: str
    agent_id: str
    action_type: str = Field(min_length=1)
    target_service: str = Field(min_length=1)
    payload: dict[str, object]
    signature: str = Field(min_length=1)
    capability_token: str = Field(min_length=1)
    request_context: dict[str, object] = Field(default_factory=dict)


app = FastAPI(title="Limiq.io FastAPI Target Example")
KYA_BASE_URL = os.getenv("KYA_BASE_URL", "http://localhost:8000")


def _safe_json(resp: httpx.Response) -> dict[str, object]:
    try:
        payload = resp.json()
    except ValueError:
        return {"raw": resp.text}

    if isinstance(payload, dict):
        return payload
    return {"raw": payload}


@app.get("/health")
async def health() -> dict[str, object]:
    return {"ok": True, "service": "fastapi-target", "kya_base_url": KYA_BASE_URL}


@app.post("/purchase")
async def purchase(data: VerifyPayload) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            verify_resp = await client.post(
                f"{KYA_BASE_URL}/verify",
                headers={"X-Workspace-Id": data.workspace_id},
                json=data.model_dump(),
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail={"error": "Limiq.io verify timeout"}) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail={"error": "Limiq.io verify unreachable"}) from exc

    verify_payload = _safe_json(verify_resp)
    if verify_resp.status_code >= 500:
        raise HTTPException(
            status_code=502,
            detail={"error": "Limiq.io verify upstream error", "upstream": verify_payload},
        )
    if verify_resp.status_code >= 400:
        raise HTTPException(
            status_code=verify_resp.status_code,
            detail={"error": "Limiq.io verify request rejected", "upstream": verify_payload},
        )

    decision = verify_payload.get("decision")
    if decision != "ALLOW":
        raise HTTPException(status_code=403, detail=verify_payload)

    return {
        "ok": True,
        "executed": True,
        "audit_event_id": verify_payload.get("audit_event_id"),
    }
