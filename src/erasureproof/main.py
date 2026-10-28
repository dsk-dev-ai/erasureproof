"""FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse

from . import __version__
from .api.routes import (
    api_keys,
    connectors,
    exposure,
    governance,
    onboarding,
    overview,
    requests,
    subjects,
    system,
    tenants,
)
from .config import get_settings, validate_runtime_settings
from .middleware import ProductionMiddleware
from .models.db import get_database


def _web_root() -> Path:
    root = Path(get_settings().web_dir)
    if not root.is_absolute():
        root = Path.cwd() / root
    return root.resolve()


def _web_index() -> Path:
    index = _web_root() / "index.html"
    if not index.is_file():
        raise HTTPException(
            status_code=404,
            detail="console build not found; run `cd web && npm install && npm run build`",
        )
    return index


def _configure_logging() -> None:
    logger = logging.getLogger("erasureproof")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_runtime_settings(get_settings())
    get_database().create_all()
    yield


def create_app() -> FastAPI:
    _configure_logging()
    settings = get_settings()
    application = FastAPI(
        title="ErasureProof",
        version=__version__,
        description=(
            "Find every copy of a person's data, remediate it in dependency order, "
            "verify the result and issue a signed proof of erasure.\n\n"
            "Authenticate with `Authorization: Bearer <api_key>` or `X-API-Key`. "
            "Create a free sandbox with `POST /v1/onboarding/sandbox`."
        ),
        contact={
            "name": "ErasureProof",
            "url": "https://github.com/dsk-dev-ai/erasureproof",
        },
        license_info={"name": "Apache-2.0"},
        openapi_tags=[
            {"name": "system", "description": "Health, metrics, policies and integrity."},
            {"name": "onboarding", "description": "Self-service sandbox provisioning."},
            {"name": "tenants", "description": "Workspace lifecycle and isolation."},
            {"name": "api-keys", "description": "Hashed, revocable tenant API keys."},
            {"name": "subjects", "description": "Current and historical identity graphs."},
            {"name": "connectors", "description": "Customer-system discovery connectors."},
            {"name": "requests", "description": "Deletion audits, plans and attestations."},
            {"name": "governance", "description": "Approvals, audit events and exports."},
            {"name": "overview", "description": "Workspace metrics and operational state."},
            {"name": "exposure", "description": "Authorized passive exposure checks."},
        ],
        lifespan=lifespan,
    )
    if settings.cors_origin_list:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
            expose_headers=["X-Request-ID", "X-RateLimit-Limit", "Retry-After"],
        )
    application.add_middleware(ProductionMiddleware)
    application.include_router(system.router, tags=["system"])
    application.include_router(onboarding.router, tags=["onboarding"])
    application.include_router(api_keys.router, tags=["api-keys"])
    application.include_router(governance.router, tags=["governance"])
    application.include_router(overview.router, tags=["overview"])
    application.include_router(tenants.router, tags=["tenants"])
    application.include_router(subjects.router, tags=["subjects"])
    application.include_router(connectors.router, tags=["connectors"])
    application.include_router(requests.router, tags=["requests"])
    application.include_router(exposure.router, tags=["exposure"])

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "ErasureProof",
            "version": __version__,
            "docs": "/docs",
            "health": "/healthz",
            "console": "/console",
            "sandbox": "/v1/onboarding/sandbox",
            "api_keys": "/v1/api-keys",
        }

    @application.api_route("/console", methods=["GET", "HEAD"], include_in_schema=False)
    def console_root() -> FileResponse:
        return FileResponse(_web_index(), headers={"Cache-Control": "no-cache"})

    @application.api_route(
        "/console/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False
    )
    def console_assets(full_path: str) -> FileResponse:
        index = _web_index()
        root = _web_root()
        candidate = (root / full_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            candidate = index
        if candidate.is_file():
            cache = (
                "public, max-age=31536000, immutable"
                if full_path.startswith("assets/")
                else "no-cache"
            )
            return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    def custom_openapi() -> dict:
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(
            title=application.title,
            version=application.version,
            description=application.description,
            routes=application.routes,
            contact=application.contact,
            license_info=application.license_info,
            tags=application.openapi_tags,
        )
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {}).update(
            {
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "ApiKeyAuth": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            }
        )
        for path, methods in schema.get("paths", {}).items():
            if not path.startswith("/v1") or path == "/v1/onboarding/sandbox":
                continue
            for operation in methods.values():
                if isinstance(operation, dict):
                    operation.setdefault(
                        "security", [{"BearerAuth": []}, {"ApiKeyAuth": []}]
                    )
        application.openapi_schema = schema
        return schema

    application.openapi = custom_openapi  # type: ignore[method-assign]

    return application


app = create_app()
