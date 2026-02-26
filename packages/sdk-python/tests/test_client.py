import asyncio

import httpx

from limiq_sdk.client import AsyncLimiqClient, LimiqClient


def _verify_payload() -> dict[str, object]:
    return {
        "workspace_id": "workspace-1",
        "agent_id": "agent-1",
        "action_type": "purchase",
        "target_service": "stripe_proxy",
        "payload": {"amount": 18},
        "signature": "sig",
        "capability_token": "tok",
        "request_context": {},
    }


def test_sync_client_verify_action() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/verify"
        assert request.headers["X-Workspace-Id"] == "workspace-1"
        return httpx.Response(
            status_code=200,
            json={
                "decision": "ALLOW",
                "reason_code": None,
                "audit_event_id": "00000000-0000-0000-0000-000000000000",
            },
        )

    sdk = LimiqClient(
        base_url="http://example.test",
        workspace_id="workspace-1",
        transport=httpx.MockTransport(handler),
    )

    result = sdk.verify_action(_verify_payload())
    assert result["decision"] == "ALLOW"


def test_async_client_verify_action() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/verify"
        assert request.headers["X-Workspace-Id"] == "workspace-1"
        return httpx.Response(
            status_code=200,
            json={
                "decision": "DENY",
                "reason_code": "SIGNATURE_INVALID",
                "audit_event_id": "00000000-0000-0000-0000-000000000001",
            },
        )

    sdk = AsyncLimiqClient(
        base_url="http://example.test",
        workspace_id="workspace-1",
        transport=httpx.MockTransport(handler),
    )

    async def run() -> None:
        result = await sdk.verify_action(_verify_payload())
        assert result["decision"] == "DENY"

    asyncio.run(run())
