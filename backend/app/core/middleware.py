"""HTTP middleware: X-Run-Id propagation. Per observability.md."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import ulid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RunIdMiddleware(BaseHTTPMiddleware):
    """Read X-Run-Id from incoming request or generate one; echo it on the response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("X-Run-Id")
        run_id = incoming if incoming else str(ulid.new())
        request.state.run_id = run_id

        response: Response = await call_next(request)
        response.headers["X-Run-Id"] = run_id
        return response
