import base64
import logging
from hashlib import sha256
from typing import cast

import pytest
from fastapi.testclient import TestClient
from nacl.signing import SigningKey

from app.modules.verify_engine.canonical_json import canonical_json_bytes


def _setup_agent_policy_capability(
    client: TestClient, workspace_id: str
) -> tuple[str, SigningKey, dict[str, object]]:
    signing_key = SigningKey.generate()
    public_key_b64 = base64.b64encode(bytes(signing_key.verify_key)).decode()

    agent = client.post(
        "/agents",
        json={
            "workspace_id": workspace_id,
            "name": "agent-logs",
            "public_key": public_key_b64,
            "metadata": {},
        },
    )
    assert agent.status_code == 201
    agent_id = str(agent.json()["id"])

    policy = client.post(
        "/policies",
        json={
            "workspace_id": workspace_id,
            "name": "policy-logs",
            "version": 1,
            "schema_version": 1,
            "policy_json": {
                "allowed_tools": ["purchase"],
                "spend": {"currency": "EUR", "max_per_tx": 50},
                "rate_limits": {"max_actions_per_min": 10},
            },
        },
    )
    assert policy.status_code == 201

    bind = client.post(
        f"/agents/{agent_id}/bind_policy",
        json={"workspace_id": workspace_id, "policy_id": policy.json()["id"]},
        headers={"X-Workspace-Id": workspace_id},
    )
    assert bind.status_code == 201

    capability = client.post(
        "/capabilities/request",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action": "purchase",
            "target_service": "stripe_proxy",
            "requested_scopes": ["purchase"],
            "requested_limits": {"amount": 18, "currency": "EUR"},
            "ttl_minutes": 15,
        },
        headers={"X-Workspace-Id": workspace_id},
    )
    assert capability.status_code == 201
    return agent_id, signing_key, cast(dict[str, object], capability.json())


def test_observability_logs_include_correlation_fields(
    client: TestClient,
    workspace_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    agent_id, signing_key, capability = _setup_agent_policy_capability(client, workspace_id)

    payload = {"amount": 18, "currency": "EUR", "tool": "purchase"}
    envelope = {
        "agent_id": agent_id,
        "workspace_id": workspace_id,
        "action_type": "purchase",
        "target_service": "stripe_proxy",
        "payload": payload,
        "capability_jti": str(capability["jti"]),
    }
    signature = base64.b64encode(
        signing_key.sign(sha256(canonical_json_bytes(envelope)).digest()).signature
    ).decode()

    verify = client.post(
        "/verify",
        json={
            "workspace_id": workspace_id,
            "agent_id": agent_id,
            "action_type": "purchase",
            "target_service": "stripe_proxy",
            "payload": payload,
            "signature": signature,
            "capability_token": capability["token"],
            "request_context": {},
        },
        headers={"X-Workspace-Id": workspace_id},
    )
    assert verify.status_code == 200

    integrity = client.get(
        f"/audit/integrity/check?workspace_id={workspace_id}",
        headers={"X-Workspace-Id": workspace_id},
    )
    assert integrity.status_code == 200

    verify_logs = [
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "verify_decision"
    ]
    assert verify_logs
    verify_record = verify_logs[-1]
    assert getattr(verify_record, "workspace_id", None) == workspace_id
    assert getattr(verify_record, "agent_id", None) == agent_id
    assert getattr(verify_record, "decision", None) == "ALLOW"
    assert getattr(verify_record, "audit_event_id", None) is not None

    integrity_logs = [
        record
        for record in caplog.records
        if getattr(record, "event_name", None) == "audit_integrity_checked"
    ]
    assert integrity_logs
    integrity_record = integrity_logs[-1]
    assert getattr(integrity_record, "workspace_id", None) == workspace_id
    assert getattr(integrity_record, "status", None) in {"OK", "BROKEN", "PARTIAL"}
    assert getattr(integrity_record, "checked_count", None) is not None

    http_logs = [
        record for record in caplog.records if getattr(record, "event_name", None) == "http_request"
    ]
    assert http_logs
    assert any(getattr(record, "path", None) == "/verify" for record in http_logs)
    assert all(getattr(record, "status", None) is not None for record in http_logs)
    assert all(getattr(record, "latency_ms", None) is not None for record in http_logs)
