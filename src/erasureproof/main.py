"""FastAPI application."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api.routes import connectors, exposure, requests, subjects, system, tenants
from .models.db import get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_database().create_all()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="ErasureProof",
        version=__version__,
        description=(
            "Find every copy of a person's data, remediate it in dependency order, "
            "verify the result and issue a signed proof of erasure."
        ),
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(system.router, tags=["system"])
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
        }

    return application


app = create_app()
