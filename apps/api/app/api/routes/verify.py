import logging
from time import perf_counter
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthContext, ensure_workspace_match, get_auth_context
from app.core.openapi import COMMON_ERROR_RESPONSES
from app.db.session import get_db
from app.modules.verify_engine.service import verify_action
from app.observability.metrics import observe_verify
from app.schemas.verify import VerifyRequest, VerifyResponse

router = APIRouter(tags=["verify"])
DbSession = Annotated[Session, Depends(get_db)]
Auth = Annotated[AuthContext, Depends(get_auth_context)]
logger = logging.getLogger("kya.verify")


def _extract_jti_unverified(token: str) -> str | None:
    try:
        claims = jwt.decode(
            token,
            key="",
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_aud": False,
                "verify_iss": False,
            },
            algorithms=["EdDSA", "HS256", "RS256"],
        )
    except jwt.DecodeError:
        # Used for logging/metrics only; not security-critical for decisions.
        logger.debug("jti_extraction_failed", exc_info=True)
        return None
    except Exception:
        # Used for logging/metrics only; not security-critical for decisions.
        logger.debug("jti_extraction_failed", exc_info=True)
        return None

    jti = claims.get("jti")
    return str(jti) if isinstance(jti, str) else None


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify Action",
    description=(
        "Validates an agent action request against capability token, signature, "
        "policy binding and runtime constraints."
    ),
    responses=COMMON_ERROR_RESPONSES,
)
def verify_endpoint(payload: VerifyRequest, auth: Auth, db: DbSession) -> VerifyResponse:
    ensure_workspace_match(auth.workspace_id, payload.workspace_id)
    start = perf_counter()
    response = verify_action(db, payload)
    latency_seconds = perf_counter() - start

    observe_verify(
        decision=response.decision,
        reason_code=response.reason_code,
        latency_seconds=latency_seconds,
    )
    logger.info(
        "verify_decision",
        extra={
            "event_name": "verify_decision",
            "workspace_id": str(payload.workspace_id),
            "agent_id": str(payload.agent_id),
            "jti": _extract_jti_unverified(payload.capability_token),
            "decision": response.decision,
            "reason_code": response.reason_code,
            "audit_event_id": str(response.audit_event_id),
            "path": "/verify",
            "method": "POST",
        },
    )
    return response
