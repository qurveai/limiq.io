from uuid import uuid4

import pytest
from redis.exceptions import RedisError

from app.core.config import settings
from app.modules.revocation.service import check_rate_limit


class _RedisRaises:
    def incr(self, key: str) -> int:
        raise RedisError("redis down")

    def expire(self, key: str, ttl: int) -> bool:
        raise RedisError("redis down")


def test_check_rate_limit_redis_error_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.revocation.service.redis_client", _RedisRaises())
    monkeypatch.setattr(settings, "rate_limit_redis_fail_open", False)

    allowed = check_rate_limit(
        workspace_id=uuid4(),
        agent_id=uuid4(),
        action_type="purchase",
        max_actions_per_min=10,
    )

    assert allowed is False


def test_check_rate_limit_redis_error_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.revocation.service.redis_client", _RedisRaises())
    monkeypatch.setattr(settings, "rate_limit_redis_fail_open", True)

    allowed = check_rate_limit(
        workspace_id=uuid4(),
        agent_id=uuid4(),
        action_type="purchase",
        max_actions_per_min=10,
    )

    assert allowed is True
