from __future__ import annotations

from sqlalchemy.orm import Session

from ..ai.provider import Usage
from ..config import Settings
from ..models import AIUsageLog


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 2.2))


def calculate_cost(settings: Settings, usage: Usage) -> float | None:
    if settings.ai_input_cost_per_million is None or settings.ai_output_cost_per_million is None:
        return None
    return round(
        ((usage.input_tokens or 0) / 1_000_000) * settings.ai_input_cost_per_million
        + ((usage.output_tokens or 0) / 1_000_000) * settings.ai_output_cost_per_million,
        8,
    )


def save_usage(
    db: Session,
    settings: Settings,
    *,
    request_id: str,
    user_id: str | None,
    feature: str,
    model: str,
    usage: Usage,
    latency_ms: int | None,
    status: str = "success",
    error_code: str | None = None,
) -> AIUsageLog:
    log = AIUsageLog(
        request_id=request_id,
        user_id=user_id,
        feature=feature,
        provider=settings.ai_provider,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        usage_estimated=usage.estimated,
        estimated_cost=calculate_cost(settings, usage),
        latency_ms=latency_ms,
        status=status,
        error_code=error_code,
    )
    db.add(log)
    db.commit()
    return log

