# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A [FastMCP](https://modelcontextprotocol.io) server that exposes Ireland's open-data
catalogue ([data.gov.ie](https://data.gov.ie)) as read-only tools. It wraps the public
**CKAN 2.9 Action API** — no authentication, nothing is ever mutated remotely.

## Commands

```bash
uv sync                       # install deps into .venv (Python 3.12)
uv run data-gov-ie-mcp        # run the server over stdio (default transport)
MCP_TRANSPORT=http MCP_PORT=8000 uv run data-gov-ie-mcp   # serve over streamable HTTP
docker compose up --build     # build + run the HTTP server in a container (:8000/mcp)
./scripts/publish.sh <tag>    # build + push michaelkerrin/data-gov-ie-mcp:<tag> to Docker Hub
```

The `Dockerfile` (uv base image, multi-layer so deps cache separately from
source) is HTTP-only by design: it sets `MCP_TRANSPORT=http`, `MCP_HOST=0.0.0.0`
(stdio/127.0.0.1 defaults would make the container unreachable). The
`HEALTHCHECK` is a TCP connect to the port — a GET on `/mcp` returns 406 (it
wants POST), so a status-code check would be misleading.

There is **no test suite** in the repo. To exercise the API layer manually, call the
client directly rather than going through the MCP transport:

```bash
uv run python -c "import asyncio; from data_gov_ie_mcp.client import call_action; \
print(asyncio.run(call_action('package_search', {'q': 'housing', 'rows': 1}))['count'])"
```

## Architecture

Two source files, one strict layering rule — **tools never call `httpx` directly**:

- **`src/data_gov_ie_mcp/client.py`** — the single chokepoint. `call_action(action, params)`
  is the *only* function that touches the network. It builds `{base}/api/3/action/{action}`,
  sends params as a GET query (dropping `None` values so optional args pass uniformly),
  unwraps CKAN's `{"success", "result", "error"}` envelope, and raises `CKANError`
  (a `ToolError` subclass, so the message reaches the MCP client) on any failure.
  Because every request funnels through here, cross-cutting concerns (logging, retries,
  caching) belong in this function — not in the tools.

- **`src/data_gov_ie_mcp/server.py`** — the `FastMCP` instance plus 8 thin tool wrappers.
  Each tool is an `async def` decorated with `@mcp.tool(annotations=_READONLY)` that
  validates its arguments via `Annotated[..., Field(...)]` and delegates to `call_action`.
  Tool docstrings and `Field` descriptions are **prompt surface** — the model reads them
  to decide what to call, so keep them accurate and specific.

- **`main.py`** — convenience entry point equivalent to the `data-gov-ie-mcp` console script.

### Adding a tool

Add an `async def` to `server.py`, decorate with `@mcp.tool(annotations=_READONLY)`,
describe each parameter with `Annotated[type, Field(description=...)]`, and return
`await call_action("<ckan_action>", {...})`. No client changes are needed unless the
CKAN action needs POST or special handling. Mirror the new tool in the README's tool table.

## Working with the live server

The server is registered as a local stdio MCP (see `.mcp.json`) and launched via
`uv run`, so a **reconnect picks up source edits automatically** — no reinstall. After
changing `client.py` or `server.py`, the already-running process keeps the old code until
you reconnect it (`/mcp` → reconnect `data-gov-ie`) or restart the session. Verify changes
by calling the client directly (above) rather than assuming the live tools reflect them.

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | HTTP bind address. |
| `DATA_GOV_IE_BASE_URL` | `https://data.gov.ie` | Point at another CKAN instance/mirror. |