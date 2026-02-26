from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import raise_http_error
from app.models.policy import Policy
from app.models.workspace import Workspace
from app.modules.audit_log.service import append_audit_event
from app.modules.policy_service.schema import PolicySchema
from app.schemas.policy import PolicyCreateRequest


def create_policy(db: Session, payload: PolicyCreateRequest) -> Policy:
    workspace = db.scalar(select(Workspace).where(Workspace.id == payload.workspace_id))
    if workspace is None:
        raise_http_error(404, "WORKSPACE_NOT_FOUND", "Workspace not found")

    try:
        PolicySchema.model_validate(payload.policy_json)
    except ValidationError as exc:
        raise_http_error(422, "POLICY_SCHEMA_INVALID", str(exc))

    policy = Policy(
        workspace_id=payload.workspace_id,
        name=payload.name,
        version=payload.version,
        is_active=True,
        schema_version=payload.schema_version,
        policy_json=payload.policy_json,
    )

    db.add(policy)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise_http_error(409, "POLICY_VERSION_ALREADY_EXISTS", "Policy version already exists")

    append_audit_event(
        db,
        workspace_id=payload.workspace_id,
        event_type="policy.created",
        subject_type="policy",
        subject_id=policy.id,
        event_data={
            "workspace_id": str(payload.workspace_id),
            "name": payload.name,
            "version": payload.version,
        },
    )

    db.commit()
    db.refresh(policy)
    return policy


def get_policy_in_workspace(db: Session, *, policy_id: UUID, workspace_id: UUID) -> Policy | None:
    return db.scalar(
        select(Policy).where(Policy.id == policy_id, Policy.workspace_id == workspace_id)
    )
