import logging
from hashlib import sha256
from typing import Literal
from uuid import UUID

import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ed25519_verify import verify_ed25519_signature
from app.core.jwt_tokens import decode_capability_token
from app.core.reason_codes import ReasonCode
from app.models.agent import Agent
from app.models.agent_policy_binding import AgentPolicyBinding
from app.models.capability import Capability
from app.models.policy import Policy
from app.modules.audit_log.service import append_audit_event
from app.modules.revocation.service import is_jti_revoked
from app.modules.verify_engine.canonical_json import canonical_json_bytes
from app.modules.verify_engine.policy_eval import (
    policy_allows_payload_spend,
    policy_allows_rate,
    scopes_allow_action,
)
from app.schemas.verify import VerifyRequest, VerifyResponse

logger = logging.getLogger("kya.verify_engine")


def _decision(
    db: Session,
    *,
    workspace_id: UUID,
    decision: Literal["ALLOW", "DENY"],
    reason_code: str | None,
    agent_id: UUID,
    event_data: dict[str, object],
) -> VerifyResponse:
    event_type = (
        "action.verification.allowed" if decision == "ALLOW" else "action.verification.denied"
    )
    enriched_event_data: dict[str, object] = {
        "decision": decision,
        "reason_code": reason_code,
        **event_data,
    }
    if reason_code is not None and "reason" not in enriched_event_data:
        enriched_event_data["reason"] = reason_code

    event = append_audit_event(
        db,
        workspace_id=workspace_id,
        event_type=event_type,
        subject_type="agent",
        subject_id=agent_id,
        event_data=enriched_event_data,
    )
    db.commit()
    return VerifyResponse(decision=decision, reason_code=reason_code, audit_event_id=event.id)


def verify_action(db: Session, payload: VerifyRequest) -> VerifyResponse:
    append_audit_event(
        db,
        workspace_id=payload.workspace_id,
        event_type="action.verification.requested",
        subject_type="agent",
        subject_id=payload.agent_id,
        event_data={
            "workspace_id": str(payload.workspace_id),
            "agent_id": str(payload.agent_id),
            "action_type": payload.action_type,
            "target_service": payload.target_service,
        },
    )
    db.flush()

    agent = db.scalar(
        select(Agent).where(
            Agent.id == payload.agent_id,
            Agent.workspace_id == payload.workspace_id,
        )
    )
    if agent is None:
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.AGENT_NOT_FOUND,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.AGENT_NOT_FOUND},
        )

    if agent.status != "active":
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.AGENT_REVOKED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.AGENT_REVOKED},
        )

    try:
        claims = decode_capability_token(payload.capability_token)
    except jwt.ExpiredSignatureError:
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_EXPIRED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_EXPIRED},
        )
    except (jwt.DecodeError, jwt.InvalidTokenError):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_INVALID,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_INVALID},
        )
    except Exception:
        logger.error("unexpected_error_decoding_capability_token", exc_info=True)
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_INVALID,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_INVALID},
        )

    token_agent_id = str(claims.get("sub", ""))
    token_workspace_id = str(claims.get("workspace_id", ""))
    jti = str(claims.get("jti", ""))

    if token_agent_id != str(payload.agent_id) or token_workspace_id != str(payload.workspace_id):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.WORKSPACE_MISMATCH,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.WORKSPACE_MISMATCH},
        )

    if is_jti_revoked(db, jti=jti):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_REVOKED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_REVOKED, "jti": jti},
        )

    capability = db.scalar(select(Capability).where(Capability.jti == jti))
    if capability is None or capability.status != "active":
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_REVOKED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_REVOKED, "jti": jti},
        )

    scopes_raw = claims.get("scopes", [])
    scopes = [str(scope) for scope in scopes_raw] if isinstance(scopes_raw, list) else []
    tool = payload.payload.get("tool")
    tool_str = str(tool) if tool is not None else None

    if not scopes_allow_action(scopes=scopes, action_type=payload.action_type, tool=tool_str):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.CAPABILITY_SCOPE_MISMATCH,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.CAPABILITY_SCOPE_MISMATCH, "jti": jti},
        )

    signed_envelope: dict[str, object] = {
        "agent_id": str(payload.agent_id),
        "workspace_id": str(payload.workspace_id),
        "action_type": payload.action_type,
        "target_service": payload.target_service,
        "payload": payload.payload,
        "capability_jti": jti,
    }
    canonical = canonical_json_bytes(signed_envelope)
    payload_hash = sha256(canonical).digest()

    if not verify_ed25519_signature(
        public_key_b64=agent.public_key,
        message=payload_hash,
        signature_b64=payload.signature,
    ):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.SIGNATURE_INVALID,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.SIGNATURE_INVALID},
        )

    binding = db.scalar(
        select(AgentPolicyBinding).where(
            AgentPolicyBinding.workspace_id == payload.workspace_id,
            AgentPolicyBinding.agent_id == payload.agent_id,
            AgentPolicyBinding.status == "active",
        )
    )
    if binding is None:
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.POLICY_NOT_BOUND,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.POLICY_NOT_BOUND},
        )

    policy = db.scalar(
        select(Policy).where(
            Policy.id == binding.policy_id,
            Policy.workspace_id == payload.workspace_id,
            Policy.is_active.is_(True),
        )
    )
    if policy is None:
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.POLICY_NOT_BOUND,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.POLICY_NOT_BOUND},
        )

    if not policy_allows_payload_spend(policy_json=policy.policy_json, payload=payload.payload):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.SPEND_LIMIT_EXCEEDED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.SPEND_LIMIT_EXCEEDED},
        )

    if not policy_allows_rate(
        policy_json=policy.policy_json,
        workspace_id=payload.workspace_id,
        agent_id=payload.agent_id,
        action_type=payload.action_type,
    ):
        return _decision(
            db,
            workspace_id=payload.workspace_id,
            decision="DENY",
            reason_code=ReasonCode.RATE_LIMIT_EXCEEDED,
            agent_id=payload.agent_id,
            event_data={"reason": ReasonCode.RATE_LIMIT_EXCEEDED},
        )

    return _decision(
        db,
        workspace_id=payload.workspace_id,
        decision="ALLOW",
        reason_code=None,
        agent_id=payload.agent_id,
        event_data={"jti": jti, "action_type": payload.action_type},
    )
