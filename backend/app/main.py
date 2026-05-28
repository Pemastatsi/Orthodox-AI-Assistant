"""FastAPI app factory.

T-001 shipped /health and the production-auth boot guard. T-002 mounts the ingest + corpus
routers under /api/v1 and wires the SQLAlchemy engine + Redis pool lifecycles.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.v1._deps import shutdown_query_resources, shutdown_redis
from app.api.v1.admin import router as admin_router
from app.api.v1.corpus import router as corpus_router
from app.api.v1.ingest import router as ingest_router
from app.api.v1.query import router as query_router
from app.core.auth import log_auth_startup
from app.core.config import Settings, get_settings
from app.core.errors import ProductionAuthConfigError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RunIdMiddleware
from app.domain.repositories._base import dispose_engine, init_engine
from app.domain.services.encryption_service import load_key_map_from_env
from app.domain.services.safety_config import (
    assert_production_ready,
    load_pastoral_filters,
    load_sensitivity_keywords,
)


def _production_auth_guard(settings: Settings) -> None:
    """Refuse to boot when APP_ENV=production and AUTH_PROVIDER=dev.

    See auth-context.md §Boot guard."""
    if settings.app_env == "production" and settings.auth_provider == "dev":
        raise ProductionAuthConfigError(
            "AUTH_PROVIDER=dev is not allowed when APP_ENV=production. "
            "Set AUTH_PROVIDER=clerk before deploying to production."
        )


def _production_sensitive_log_guard(settings: Settings) -> None:
    """Refuse to boot when APP_ENV=production and SENSITIVE_LOG_DATA_KEY_BASE64
    is missing or malformed. Without this guard the key is only validated on the
    first sensitive query, so a misconfigured production deploy ships and then
    crashes per-request. See ADR-0005 §Encryption strategy."""
    if settings.app_env != "production":
        return
    load_key_map_from_env(
        settings.sensitive_log_data_key_base64,
        settings.sensitive_log_key_version,
    )


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    _production_auth_guard(settings)
    _production_sensitive_log_guard(settings)
    log_auth_startup(settings)

    # Safety config self-test per docs/contracts/safety-config-format.md §Phase 2 Launch Gate.
    safety_config = load_sensitivity_keywords(settings.sensitivity_keywords_path)
    assert_production_ready(safety_config, app_env=settings.app_env)
    # Pastoral filters are validated at startup too; A6 fails closed if the file is missing.
    load_pastoral_filters(settings.pastoral_filters_path)

    app = FastAPI(
        title="Orthodox AI Assistant",
        version=settings.service_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(RunIdMiddleware)

    logger = get_logger(__name__)

    @app.on_event("startup")
    async def _startup() -> None:
        init_engine(settings)

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await dispose_engine()
        await shutdown_redis()
        await shutdown_query_resources()

    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": settings.service_version,
                "appEnv": settings.app_env,
            }
        )

    app.include_router(ingest_router, prefix="/api/v1")
    app.include_router(corpus_router, prefix="/api/v1")
    app.include_router(query_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    logger.info(
        "app.startup",
        service="backend",
        version=settings.service_version,
        app_env=settings.app_env,
    )

    return app


app = create_app()
