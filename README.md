# data-gov-ie-mcp

An [MCP](https://modelcontextprotocol.io) server that exposes Ireland's open-data
catalogue — [data.gov.ie](https://data.gov.ie) — as tools for Claude. It wraps the
public **CKAN 2.9 Action API**; all tools are read-only and need no authentication.

## Tools

| Tool | What it does |
|------|--------------|
| `package_search` | Search the dataset catalogue (primary discovery tool). |
| `package_show` | Full metadata for one dataset, including its resources (files/APIs). |
| `package_list` | Paged list of dataset names (slugs). |
| `resource_search` | Search individual resources by `field:term` (e.g. `format:CSV`). |
| `tag_list` | List tags, optionally filtered by substring. |
| `tag_show` | Details for one tag, optionally with its datasets. |
| `organization_list` | List data publishers (for `organization:<name>` filters). |
| `group_list` | List themes/categories (for `groups:<name>` filters). |

## Run

```bash
uv sync
uv run data-gov-ie-mcp     # stdio transport (default)
```

To serve over streamable HTTP instead (same tool code):

```bash
MCP_TRANSPORT=http MCP_PORT=8000 uv run data-gov-ie-mcp
```

## Docker

Build and run the HTTP server in a container (endpoint at
`http://127.0.0.1:8000/mcp`):

```bash
docker compose up --build          # or: docker build -t data-gov-ie-mcp . && \
                                   #     docker run -p 8000:8000 data-gov-ie-mcp
```

The image bakes in the HTTP transport and binds `0.0.0.0` so the port is
reachable from the host (the bare code defaults to `127.0.0.1`, which a
container won't expose). Request logs go to stderr, so `docker logs` shows
them. Override any [env var](#configuration) with `-e` / the compose
`environment:` block.

## Use it in Claude Code

Register the server as a local stdio MCP:

```bash
claude mcp add data-gov-ie -- uv run --directory /home/michael/src/opendatamcp/data-gov-ie-mcp data-gov-ie-mcp
```

Then ask things like *"find CSV datasets about housing in Dublin"* or
*"show me the resources in the-walled-towns-of-ireland dataset"*.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `MCP_TRANSPORT` | `stdio` | `stdio` or `http`. |
| `MCP_HOST` / `MCP_PORT` | `127.0.0.1` / `8000` | HTTP bind address. |
| `DATA_GOV_IE_BASE_URL` | `https://data.gov.ie` | Point at another CKAN instance/mirror. |

## Project layout

```
src/data_gov_ie_mcp/
  client.py   # thin async CKAN Action API client (envelope unwrap + errors)
  server.py   # FastMCP server + the 8 tool definitions
main.py       # `python main.py` convenience entry point
```
