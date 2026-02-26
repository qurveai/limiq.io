import base64
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import UUID

import jwt
import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.jwt_tokens import decode_capability_token, encode_capability_token
from app.models.audit_event import AuditEvent
from app.models.capability import Capability
from app.modules.revocation.service import blacklist_jti_until_expiry
from app.modules.verify_engine.canonical_json import canonical_json_bytes

PRIV_KEY = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MC4CAQAwBQYDK2VwBCIEIL1+Klzp5E0gHEu8KSBoLuWCxKDLdmgjxNmo3FNARcVl\n"
    "-----END PRIVATE KEY-----"
)


def _generate_agent_keypair() -> tuple[str, SigningKey]:
    signing_key = SigningKey.generate()
    verify_key = signing_key.verify_key
    public_key_b64 = base64.b64encode(bytes(verify_key)).decode()
    return public_key_b64, signing_key


def _create_agent(client: TestClient, workspace_id: str, public_key_b64: str) -> str:
    response = client.post(
        "/agents",
        json={
            "workspace_id": workspace_id,
            "name": "agent-verify",
            "public_key": public_key_b64,
            "metadata": {},
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


def _auth_headers(workspace_id: str) -> dict[str, str]:
    return {"X-Workspace-Id": workspace_id}


def _create_policy_and_bind(
    client: TestClient,
    workspace_id: str,
    agent_id: str,
    *,
    max_per_tx: int = 50,
    max_actions_per_min: int = 10,
) -> None:
    policy = client.post(
        "/policies",
        json={
            "workspace_id": workspace_id,
            "name": "purchase_verify",
            "version": 1,
            "schema_version": 1,
            "policy_json": {
                "allowed_tools": ["purchase"],
                "spend": {"currency": "EUR", "max_per_tx": max_per_tx},
                "rate_limits": {"max_actions_per_min": max_actions_per_min},
            },
        },
    )
    assert policy.status_code == 201
    policy_id = str(policy.json()["id"])

    bind = client.post(
        f"/agents/{agent_id}/bind_policy",
        json={"workspace_id": workspace_id, "policy_id": policy_id},
        headers=_auth_headers(workspace_id),
    )
    assert bind.status_code == 201


def _issue_capability(
    client: TestClient,
    workspace_id: str,
    agent_id: str,
    scopes: list[str],
) -> dict[str, object]:
    response = client.post(
        "/capabilities/request",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action": "purchase",
            "target_service": "stripe_proxy",
            "requested_scopes": scopes,
            "requested_limits": {"amount": 20, "currency": "EUR"},
            "ttl_minutes": 15,
        },
        headers=_auth_headers(workspace_id),
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def _sign_request(
    *,
    signing_key: SigningKey,
    workspace_id: str,
    agent_id: str,
    action_type: str,
    target_service: str,
    payload: dict[str, object],
    capability_jti: str,
) -> str:
    envelope = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "action_type": action_type,
        "target_service": target_service,
        "payload": payload,
        "capability_jti": capability_jti,
    }
    canonical = canonical_json_bytes(envelope)
    digest = sha256(canonical).digest()
    signature = signing_key.sign(digest).signature
    return base64.b64encode(signature).decode()


def test_verify_allow_happy_path(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    jti = str(issued["jti"])
    payload = {"amount": 18, "currency": "EUR", "tool": "deploy_prod"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=jti,
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
            "request_context": {"ip": "127.0.0.1"},
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "ALLOW"
    assert response.json()["reason_code"] is None


def test_verify_deny_capability_expired(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    claims = decode_capability_token(str(issued["token"]))
    claims["exp"] = int((datetime.now(tz=UTC) - timedelta(minutes=1)).timestamp())
    expired_token = jwt.encode(
        claims,
        PRIV_KEY,
        algorithm="EdDSA",
        headers={"kid": "test-ed25519-key-1"},
    )

    payload = {"amount": 18, "currency": "EUR", "tool": "deploy_prod"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": expired_token,
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "CAPABILITY_EXPIRED"


def test_verify_deny_capability_revoked(
    client: TestClient,
    workspace_id: str,
    db_session: Session,
) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    jti = str(issued["jti"])
    capability = db_session.scalar(select(Capability).where(Capability.jti == jti))
    assert capability is not None
    capability.status = "revoked"
    db_session.commit()

    claims = decode_capability_token(str(issued["token"]))
    exp_ts = int(cast(int, claims["exp"]))
    blacklist_jti_until_expiry(jti=jti, exp_timestamp=exp_ts)

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=jti,
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "CAPABILITY_REVOKED"


def test_verify_deny_scope_mismatch(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 18, "currency": "EUR", "tool": "deploy_prod"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="deploy_prod",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "deploy_prod",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "CAPABILITY_SCOPE_MISMATCH"


def test_verify_deny_invalid_signature(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti="wrong-jti",
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "SIGNATURE_INVALID"


def test_verify_deny_policy_not_bound(
    client: TestClient,
    workspace_id: str,
    db_session: Session,
) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)

    # create standalone capability token and DB row without policy binding
    jti = "9dd5d3ce-ffb9-4e2c-ad53-024d77f56700"
    claims = {
        "sub": agent_id,
        "workspace_id": workspace_id,
        "scopes": ["purchase"],
        "limits": {"amount": 20},
        "policy_id": workspace_id,
        "policy_version": 1,
        "iat": int(datetime.now(tz=UTC).timestamp()),
        "exp": int((datetime.now(tz=UTC) + timedelta(minutes=5)).timestamp()),
        "jti": jti,
    }
    token = encode_capability_token(claims)

    db_session.add(
        Capability(
            workspace_id=UUID(workspace_id),
            agent_id=UUID(agent_id),
            jti=jti,
            scopes={"items": ["purchase"]},
            limits={"amount": 20},
            status="active",
            issued_at=datetime.now(tz=UTC),
            expires_at=datetime.now(tz=UTC) + timedelta(minutes=5),
        )
    )
    db_session.commit()

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=jti,
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": token,
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "POLICY_NOT_BOUND"


def test_verify_deny_spend_limit_exceeded(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id, max_per_tx=20)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 40, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "SPEND_LIMIT_EXCEEDED"


def test_verify_deny_rate_limit_exceeded(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id, max_actions_per_min=1)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 10, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    first = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )
    second = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert first.status_code == 200
    assert first.json()["decision"] == "ALLOW"
    assert second.status_code == 200
    assert second.json()["decision"] == "DENY"
    assert second.json()["reason_code"] == "RATE_LIMIT_EXCEEDED"


def test_verify_writes_requested_and_decision_audit_events(
    client: TestClient,
    workspace_id: str,
    db_session: Session,
) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    event_types = db_session.scalars(select(AuditEvent.event_type)).all()
    assert "action.verification.requested" in event_types
    assert any(
        event_type in {"action.verification.allowed", "action.verification.denied"}
        for event_type in event_types
    )


def test_verify_workspace_mismatch_denied(client: TestClient, workspace_id: str) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers={"X-Workspace-Id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "WORKSPACE_MISMATCH"


def test_verify_deny_capability_invalid_on_unexpected_decode_error(
    client: TestClient,
    workspace_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_key_b64, signing_key = _generate_agent_keypair()
    agent_id = _create_agent(client, workspace_id, public_key_b64)
    _create_policy_and_bind(client, workspace_id, agent_id)
    issued = _issue_capability(client, workspace_id, agent_id, ["purchase"])

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    signature = _sign_request(
        signing_key=signing_key,
        workspace_id=workspace_id,
        agent_id=agent_id,
        action_type="purchase",
        target_service="stripe_proxy",
        payload=payload,
        capability_jti=str(issued["jti"]),
    )

    def _raise_unexpected(_: str) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.modules.verify_engine.service.decode_capability_token",
        _raise_unexpected,
    )

    response = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": issued["token"],
        },
        headers=_auth_headers(workspace_id),
    )

    assert response.status_code == 200
    assert response.json()["decision"] == "DENY"
    assert response.json()["reason_code"] == "CAPABILITY_INVALID"
