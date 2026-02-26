from typing import Any

import httpx

from limiq_sdk.crypto import extract_capability_jti, sign_action
from limiq_sdk.types import CapabilityRequestBody, CapabilityResponse, VerifyRequestBody, VerifyResponse


class LimiqClient:
    def __init__(
        self,
        *,
        base_url: str,
        workspace_id: str,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._workspace_id = workspace_id
        self._timeout = timeout
        self._transport = transport

    def request_capability(self, payload: CapabilityRequestBody) -> CapabilityResponse:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            response = client.post(
                f"{self._base_url}/capabilities/request",
                headers={"X-Workspace-Id": self._workspace_id},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def verify_action(self, payload: VerifyRequestBody) -> VerifyResponse:
        with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
            response = client.post(
                f"{self._base_url}/verify",
                headers={"X-Workspace-Id": self._workspace_id},
                json=payload,
            )
            response.raise_for_status()
            return response.json()


class AsyncLimiqClient:
    def __init__(
        self,
        *,
        base_url: str,
        workspace_id: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._workspace_id = workspace_id
        self._timeout = timeout
        self._transport = transport

    async def request_capability(self, payload: CapabilityRequestBody) -> CapabilityResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/capabilities/request",
                headers={"X-Workspace-Id": self._workspace_id},
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def verify_action(self, payload: VerifyRequestBody) -> VerifyResponse:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/verify",
                headers={"X-Workspace-Id": self._workspace_id},
                json=payload,
            )
            response.raise_for_status()
            return response.json()


def build_signed_request(
    *,
    workspace_id: str,
    agent_id: str,
    action_type: str,
    target_service: str,
    payload: dict[str, Any],
    capability_token: str,
    private_key_base64: str,
    request_context: dict[str, Any] | None = None,
) -> VerifyRequestBody:
    capability_jti = extract_capability_jti(capability_token)
    signed = sign_action(
        agent_id=agent_id,
        workspace_id=workspace_id,
        action_type=action_type,
        target_service=target_service,
        payload=payload,
        capability_jti=capability_jti,
        private_key_base64=private_key_base64,
    )

    return {
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "action_type": action_type,
        "target_service": target_service,
        "payload": payload,
        "signature": signed["signature_base64"],
        "capability_token": capability_token,
        "request_context": request_context or {},
    }
