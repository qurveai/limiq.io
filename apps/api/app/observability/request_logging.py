import logging
from time import perf_counter

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint

logger = logging.getLogger("kya.http")


async def request_logging_middleware(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    start = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (perf_counter() - start) * 1000
        logger.info(
            "http_request",
            extra={
                "event_name": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "latency_ms": round(latency_ms, 2),
            },
            exc_info=True,
        )
        raise

    latency_ms = (perf_counter() - start) * 1000
    logger.info(
        "http_request",
        extra={
            "event_name": "http_request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "latency_ms": round(latency_ms, 2),
        },
    )
    return response
