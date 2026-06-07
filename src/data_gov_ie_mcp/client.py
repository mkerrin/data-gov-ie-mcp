"""Thin async client for the data.gov.ie CKAN Action API.

The CKAN Action API is a uniform JSON-RPC-style interface: every action is
reached at ``{base}/api/3/action/{action}`` and responds with an envelope::

    {"help": "...", "success": true, "result": <payload>}

On failure ``success`` is ``false`` and an ``error`` object describes the
problem. We unwrap the envelope and surface ``result`` directly, raising a
``CKANError`` (a ``ToolError`` subclass, so the message reaches the client) on
any failure.
"""

from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler
from typing import Any

import httpx
from fastmcp.exceptions import ToolError

DEFAULT_BASE_URL = "https://data.gov.ie"
# data.gov.ie runs CKAN 2.9; the Action API has been stable at v3 for years.
API_PATH = "/api/3/action/"

_USER_AGENT = "data-gov-ie-mcp/0.1 (+https://github.com/opendatamcp)"

# Every outbound call to data.gov.ie is logged here. Override the path with
# DATA_GOV_IE_LOG_FILE; the rotating handler keeps the log from growing without
# bound while staying append-friendly across server restarts.
DEFAULT_LOG_FILE = "/tmp/data-gov-ie.log"


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("data_gov_ie_mcp.calls")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # don't leak request logs onto stdio (MCP transport)

    log_file = os.environ.get("DATA_GOV_IE_LOG_FILE", DEFAULT_LOG_FILE)
    # Guard against duplicate handlers if this module is imported more than once.
    already = any(
        isinstance(h, RotatingFileHandler)
        and getattr(h, "baseFilename", None) == os.path.abspath(log_file)
        for h in logger.handlers
    )
    if not already:
        handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    return logger


_logger = _build_logger()


class CKANError(ToolError):
    """A CKAN action returned an error or the request failed."""


def _base_url() -> str:
    # Allow pointing at another CKAN instance (or a mirror) without code changes.
    return os.environ.get("DATA_GOV_IE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


async def call_action(action: str, params: dict[str, Any] | None = None) -> Any:
    """Call a CKAN action and return its unwrapped ``result`` payload.

    ``params`` are sent as query-string parameters (GET), which is sufficient
    for every read-only action this server exposes. ``None`` values are dropped
    so callers can pass optional arguments uniformly.
    """
    query = {k: v for k, v in (params or {}).items() if v is not None}
    url = f"{_base_url()}{API_PATH}{action}"

    _logger.info("CALL action=%s params=%s", action, query)
    started = time.monotonic()

    def _elapsed_ms() -> int:
        return round((time.monotonic() - started) * 1000)

    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(
                url, params=query, headers={"User-Agent": _USER_AGENT}
            )
    except httpx.RequestError as exc:  # network/DNS/timeout
        _logger.error(
            "FAIL action=%s ms=%d error=request_error detail=%s",
            action, _elapsed_ms(), exc,
        )
        raise CKANError(f"Could not reach data.gov.ie: {exc}") from exc

    # CKAN returns a JSON error envelope even on 4xx/409, so try to parse first.
    try:
        body = resp.json()
    except ValueError:
        _logger.error(
            "FAIL action=%s ms=%d status=%d error=non_json",
            action, _elapsed_ms(), resp.status_code,
        )
        raise CKANError(
            f"data.gov.ie returned a non-JSON response (HTTP {resp.status_code})."
        ) from None

    if not isinstance(body, dict):
        _logger.error(
            "FAIL action=%s ms=%d status=%d error=unexpected_json_shape",
            action, _elapsed_ms(), resp.status_code,
        )
        raise CKANError(
            f"data.gov.ie returned an unexpected response shape (HTTP {resp.status_code})."
        )

    if not body.get("success", False):
        error = body.get("error", {})
        message = error.get("message") or error.get("__type") or "Unknown CKAN error"
        _logger.error(
            "FAIL action=%s ms=%d status=%d error=%s",
            action, _elapsed_ms(), resp.status_code, message,
        )
        raise CKANError(f"CKAN action '{action}' failed: {message}")

    _logger.info(
        "OK   action=%s ms=%d status=%d", action, _elapsed_ms(), resp.status_code
    )
    return body.get("result")
