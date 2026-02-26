from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes.agents import router as agents_router
from app.api.routes.audit import router as audit_router
from app.api.routes.capabilities import router as capabilities_router
from app.api.routes.health import router as health_router
from app.api.routes.metrics import router as metrics_router
from app.api.routes.policies import router as policies_router
from app.api.routes.verify import router as verify_router
from app.api.routes.workspaces import router as workspaces_router
from app.core.config import settings
from app.core.jwt_keys import validate_jwt_key_config
from app.core.openapi import API_DESCRIPTION, install_custom_openapi
from app.observability.logging import configure_logging
from app.observability.request_logging import request_logging_middleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    validate_jwt_key_config()
    yield


app = FastAPI(
    title="Limiq.io API",
    summary="Identity & Permission Layer for Autonomous Agents",
    description=API_DESCRIPTION,
    version="0.5.0",
    terms_of_service="https://github.com/qurveai/know-your-agent",
    contact={
        "name": "Limiq.io Maintainers",
        "url": "https://github.com/qurveai/know-your-agent",
    },
    license_info={"name": "Apache-2.0"},
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
    ],
    lifespan=lifespan,
)
app.openapi = install_custom_openapi(app)  # type: ignore[method-assign]
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(BaseHTTPMiddleware, dispatch=request_logging_middleware)

app.include_router(health_router)
app.include_router(workspaces_router)
app.include_router(agents_router)
app.include_router(policies_router)
app.include_router(capabilities_router)
app.include_router(verify_router)
app.include_router(audit_router)
app.include_router(metrics_router)
