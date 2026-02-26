from typing import Any, Literal, TypedDict


class VerifyEnvelope(TypedDict):
    agent_id: str
    workspace_id: str
    action_type: str
    target_service: str
    payload: dict[str, Any]
    capability_jti: str


class SignActionResult(TypedDict):
    signature_base64: str
    canonical_json: str
    sha256_hex: str


class VerifyRequestBody(TypedDict):
    workspace_id: str
    agent_id: str
    action_type: str
    target_service: str
    payload: dict[str, Any]
    signature: str
    capability_token: str
    request_context: dict[str, Any]


class VerifyResponse(TypedDict):
    decision: Literal["ALLOW", "DENY"]
    reason_code: str | None
    audit_event_id: str


class CapabilityRequestBody(TypedDict):
    workspace_id: str
    agent_id: str
    action: str
    target_service: str
    requested_scopes: list[str]
    requested_limits: dict[str, Any]
    ttl_minutes: int


class CapabilityResponse(TypedDict):
    token: str
    jti: str
    issued_at: str
    expires_at: str
