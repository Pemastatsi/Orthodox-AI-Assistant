"""FastAPI app factory. T-001 ships the /health endpoint and the production-auth boot guard.

Real API routes (query, ingest, corpus, runs, admin, tenant_config, webhooks) land in T-002+.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.auth import log_auth_startup
from app.core.config import Settings, get_settings
from app.core.errors import ProductionAuthConfigError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RunIdMiddleware


def _production_auth_guard(settings: Settings) -> None:
    """Refuse to boot when APP_ENV=production and AUTH_PROVIDER=dev.

    See auth-context.md §Boot guard."""
    if settings.app_env == "production" and settings.auth_provider == "dev":
        raise ProductionAuthConfigError(
            "AUTH_PROVIDER=dev is not allowed when APP_ENV=production. "
            "Set AUTH_PROVIDER=clerk before deploying to production."
        )


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    _production_auth_guard(settings)
    log_auth_startup(settings)

    app = FastAPI(
        title="Orthodox AI Assistant",
        version=settings.service_version,
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(RunIdMiddleware)

    logger = get_logger(__name__)

    @app.get("/health", tags=["health"])
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "version": settings.service_version,
                "appEnv": settings.app_env,
            }
        )

    logger.info(
        "app.startup",
        service="backend",
        version=settings.service_version,
        app_env=settings.app_env,
    )

    return app


app = create_app()
