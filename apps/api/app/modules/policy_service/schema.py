from pydantic import BaseModel, ConfigDict


class SpendPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str | None = None
    max_per_tx: float | None = None


class RateLimitsPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_actions_per_min: int | None = None


class PolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_tools: list[str]
    resource_scopes: list[str] | None = None
    spend: SpendPolicy | None = None
    rate_limits: RateLimitsPolicy | None = None
