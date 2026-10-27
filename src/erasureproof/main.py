"""FastAPI application."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import __version__
from .api.routes import (
    connectors,
    exposure,
    governance,
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
            "verify the result and issue a signed proof of erasure."
        ),
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

    return application


app = create_app()
