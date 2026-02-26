import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import redis_client
from app.models.capability import Capability
from app.models.revocation import Revocation

logger = logging.getLogger("kya.revocation")


def _jti_key(jti: str) -> str:
    return f"revoked:jti:{jti}"


def blacklist_jti_until_expiry(*, jti: str, exp_timestamp: int) -> None:
    ttl_seconds = max(1, exp_timestamp - int(datetime.now(tz=UTC).timestamp()))
    try:
        redis_client.setex(_jti_key(jti), ttl_seconds, "1")
    except RedisError:
        logger.warning("redis_unavailable_blacklist_write", exc_info=True)
        # Postgres remains source of truth.
        pass


def is_jti_revoked(db: Session, *, jti: str) -> bool:
    try:
        if redis_client.exists(_jti_key(jti)):
            return True
    except RedisError:
        logger.warning("redis_unavailable_revocation_check", exc_info=True)
        pass

    capability = db.scalar(select(Capability).where(Capability.jti == jti))
    if capability is not None and capability.status == "revoked":
        return True

    revocation = db.scalar(select(Revocation).where(Revocation.jti == jti))
    return revocation is not None


def check_rate_limit(
    *,
    workspace_id: UUID,
    agent_id: UUID,
    action_type: str,
    max_actions_per_min: int,
) -> bool:
    now = int(datetime.now(tz=UTC).timestamp())
    minute_bucket = now // settings.rate_limit_window_seconds
    key = f"rate:{workspace_id}:{agent_id}:{action_type}:{minute_bucket}"

    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, settings.rate_limit_redis_key_ttl_seconds)
    except RedisError:
        logger.warning(
            "redis_unavailable_rate_limit",
            extra={
                "workspace_id": str(workspace_id),
                "agent_id": str(agent_id),
                "action_type": action_type,
            },
            exc_info=True,
        )
        if settings.rate_limit_redis_fail_open:
            return True
        return False

    return count <= max_actions_per_min
