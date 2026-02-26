from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

OPENAPI_TAGS_METADATA = [
    {
        "name": "health",
        "description": "Runtime liveness/readiness checks for API, PostgreSQL and Redis.",
    },
    {
        "name": "workspaces",
        "description": "Workspace bootstrap and tenant lookup endpoints.",
    },
    {
        "name": "agents",
        "description": "Agent identity lifecycle: create, read, revoke.",
    },
    {
        "name": "policies",
        "description": "Policy registry and binding policies to agents.",
    },
    {
        "name": "capabilities",
        "description": "Capability token issuance for delegated actions.",
    },
    {
        "name": "verify",
        "description": "Verification engine endpoint returning ALLOW/DENY decisions.",
    },
    {
        "name": "audit",
        "description": "Audit trail query, export, and integrity verification.",
    },
]

API_DESCRIPTION = """
## Know Your Agent API

Identity & permission layer for autonomous agents.

### Auth model (MVP)
Sensitive routes require `X-Workspace-Id` header. The request `workspace_id` must
match this header, otherwise the API returns `WORKSPACE_MISMATCH`.

`POST /workspaces` is a bootstrap route protected by `X-Bootstrap-Token`.

### Error format
Business errors are returned as:

```json
{"detail": {"code": "SOME_CODE", "message": "Human readable message"}}
```

### Main flow
1. Create agent
2. Create policy
3. Bind policy to agent
4. Request capability
5. Verify signed action
6. Query/export audit logs
7. Check audit chain integrity
"""

COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Missing or invalid authentication headers.",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": "AUTH_WORKSPACE_MISSING",
                        "message": "Missing X-Workspace-Id header",
                    }
                }
            }
        },
    },
    403: {
        "description": "Workspace mismatch with authenticated context.",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": "WORKSPACE_MISMATCH",
                        "message": "Workspace does not match authenticated context",
                    }
                }
            }
        },
    },
    422: {
        "description": "Validation error on payload/query params.",
        "content": {
            "application/json": {
                "example": {
                    "detail": {
                        "code": "VALIDATION_ERROR",
                        "message": "Query param 'from' must be <= 'to'",
                    }
                }
            }
        },
    },
}


def install_custom_openapi(app: FastAPI) -> Callable[[], dict[str, Any]]:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            summary=app.summary,
            description=app.description,
            routes=app.routes,
            tags=OPENAPI_TAGS_METADATA,
            servers=app.servers,
            contact=app.contact,
            license_info=app.license_info,
            terms_of_service=app.terms_of_service,
        )

        schema["externalDocs"] = {
            "description": "Project documentation",
            "url": "https://github.com/qurveai/know-your-agent",
        }
        schema.setdefault("info", {})["x-logo"] = {
            "url": "https://raw.githubusercontent.com/redocly/redoc/main/demo/logo.png",
            "altText": "Know Your Agent",
        }

        app.openapi_schema = schema
        return app.openapi_schema

    return custom_openapi
