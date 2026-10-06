"""Middleware for Intervals.icu MCP server.

This module provides middleware components that run before tool execution.

Multi-tenant mode: if a request carries an `x-api-key` header, that key (plus an
optional `x-athlete-id` header) overrides the env-based credentials for this call
only. Without the header, the classic env/.env behaviour is unchanged, so existing
single-account deployments keep working.
"""

from collections.abc import Callable
from typing import Any

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

from .auth import ICUConfig, load_config, validate_credentials

API_KEY_HEADER = "x-api-key"
ATHLETE_ID_HEADER = "x-athlete-id"


def resolve_config(config: ICUConfig) -> ICUConfig:
    """Return env config, overridden by per-request headers when present.

    `x-athlete-id` is optional: "0" is Intervals' alias for "the athlete that owns
    this API key", so a key alone is enough.
    """
    headers = get_http_headers()
    key = headers.get(API_KEY_HEADER, "").strip()
    if not key:
        return config
    athlete = headers.get(ATHLETE_ID_HEADER, "").strip() or "0"
    return config.model_copy(
        update={"intervals_icu_api_key": key, "intervals_icu_athlete_id": athlete}
    )


class ConfigMiddleware(Middleware):
    """Load credentials for every tool call and inject them into ctx state.

    Priority: per-request `x-api-key` header > env / .env.
    """

    async def on_call_tool(self, context: MiddlewareContext, call_next: Callable[..., Any]):
        config = resolve_config(load_config())

        if not validate_credentials(config):
            raise ToolError(
                "Intervals.icu credentials not configured. Send an "
                "'x-api-key' header with your Intervals.icu API key "
                "(intervals.icu/settings > Developer), or run 'icu-mcp-auth'."
            )

        if context.fastmcp_context:
            await context.fastmcp_context.set_state("config", config, serializable=False)

        return await call_next(context)
