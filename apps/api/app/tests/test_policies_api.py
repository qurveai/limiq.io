from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def _policy_payload(workspace_id: str, version: int = 1) -> dict[str, object]:
    return {
        "workspace_id": workspace_id,
        "name": "purchase_basic",
        "version": version,
        "schema_version": 1,
        "policy_json": {
            "allowed_tools": ["purchase"],
            "resource_scopes": ["workspace:abc"],
            "spend": {"currency": "EUR", "max_per_tx": 50},
        },
    }


def test_create_policy_success(client: TestClient, workspace_id: str) -> None:
    response = client.post("/policies", json=_policy_payload(workspace_id))

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "purchase_basic"
    assert payload["version"] == 1


def test_create_policy_duplicate_version_conflict(client: TestClient, workspace_id: str) -> None:
    payload = _policy_payload(workspace_id)

    first = client.post("/policies", json=payload)
    second = client.post("/policies", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "POLICY_VERSION_ALREADY_EXISTS"


def test_policy_created_event_written(
    client: TestClient, workspace_id: str, db_session: Session
) -> None:
    response = client.post("/policies", json=_policy_payload(workspace_id))

    assert response.status_code == 201
    event_types = db_session.scalars(select(AuditEvent.event_type)).all()
    assert "policy.created" in event_types


def test_create_policy_workspace_mismatch_denied(client: TestClient, workspace_id: str) -> None:
    response = client.post(
        "/policies",
        json=_policy_payload(workspace_id),
        headers={"X-Workspace-Id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "WORKSPACE_MISMATCH"


def test_create_policy_rejects_unknown_top_level_field(
    client: TestClient, workspace_id: str
) -> None:
    payload = _policy_payload(workspace_id)
    payload["policy_json"] = {
        "allowed_tools": ["purchase"],
        "resource_scopes": ["workspace:abc"],
        "spend": {"currency": "EUR", "max_per_tx": 50},
        "unknown_key": True,
    }

    response = client.post("/policies", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "POLICY_SCHEMA_INVALID"


def test_create_policy_rejects_unknown_nested_spend_field(
    client: TestClient, workspace_id: str
) -> None:
    payload = _policy_payload(workspace_id)
    payload["policy_json"] = {
        "allowed_tools": ["purchase"],
        "resource_scopes": ["workspace:abc"],
        "spend": {"currency": "EUR", "max_per_trx": 50},
    }

    response = client.post("/policies", json=payload)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "POLICY_SCHEMA_INVALID"
