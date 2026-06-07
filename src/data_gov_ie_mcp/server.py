"""FastMCP server exposing data.gov.ie (CKAN) open-data actions as tools.

All tools are read-only and hit the public CKAN Action API — no auth required.
Run with ``data-gov-ie-mcp`` (stdio) or ``mcp.run(transport="http", ...)`` to
serve over streamable HTTP later without changing the tool code.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from .client import call_action

mcp = FastMCP(
    name="data-gov-ie",
    instructions=(
        "Tools for discovering and inspecting Ireland's open-data catalogue "
        "(data.gov.ie, powered by CKAN). Use package_search to find datasets, "
        "package_show to read a dataset's full metadata and its resources "
        "(downloadable files / API endpoints), and resource_search to find "
        "specific files. tag_list, organization_list and group_list help "
        "navigate by topic, publisher and theme. All data is public; nothing "
        "is modified."
    ),
)

# Every action here only reads public data and is safe to repeat.
_READONLY = {"readOnlyHint": True, "idempotentHint": True, "openWorldHint": True}


@mcp.tool(annotations=_READONLY)
async def package_search(
    q: Annotated[
        str, Field(description="Search query, e.g. 'museum' or 'housing dublin'.")
    ] = "*:*",
    rows: Annotated[
        int, Field(ge=1, le=100, description="Max datasets to return.")
    ] = 10,
    start: Annotated[
        int, Field(ge=0, description="Offset into the result set, for paging.")
    ] = 0,
    fq: Annotated[
        str | None,
        Field(
            description=(
                "Optional CKAN filter query, e.g. "
                "'organization:central-statistics-office' or 'res_format:CSV'."
            )
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Field(description="Sort order, e.g. 'metadata_modified desc' or 'score desc'."),
    ] = None,
) -> dict[str, Any]:
    """Search the data.gov.ie dataset catalogue.

    Returns a `count` (total matches) and a `results` list of dataset metadata.
    This is the primary discovery tool — start here when looking for data.
    """
    return await call_action(
        "package_search",
        {"q": q, "rows": rows, "start": start, "fq": fq, "sort": sort},
    )


@mcp.tool(annotations=_READONLY)
async def package_show(
    id: Annotated[
        str,
        Field(
            description=(
                "Dataset name (slug) or id, e.g. 'the-walled-towns-of-ireland'. "
                "Get these from package_search results."
            )
        ),
    ],
) -> dict[str, Any]:
    """Get the full metadata for one dataset, including all of its resources.

    Each resource lists a downloadable URL and format (CSV, JSON, API, etc.).
    """
    return await call_action("package_show", {"id": id})


@mcp.tool(annotations=_READONLY)
async def package_list(
    limit: Annotated[
        int, Field(ge=1, le=1000, description="Max dataset names to return.")
    ] = 100,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
) -> list[str]:
    """List dataset names (slugs) in the catalogue.

    The catalogue holds thousands of datasets, so this is paged — prefer
    package_search when you have any idea what you're looking for.
    """
    return await call_action("package_list", {"limit": limit, "offset": offset})


@mcp.tool(annotations=_READONLY)
async def resource_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Field-scoped query of the form 'field:term', e.g. "
                "'name:Walled Towns' or 'format:CSV'."
            )
        ),
    ],
    limit: Annotated[
        int, Field(ge=1, le=100, description="Max resources to return.")
    ] = 10,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
) -> dict[str, Any]:
    """Search for individual resources (files / API endpoints) across datasets.

    Returns `count` and a `results` list of resources. Use when you want a
    specific file rather than a whole dataset.
    """
    return await call_action(
        "resource_search", {"query": query, "limit": limit, "offset": offset}
    )


@mcp.tool(annotations=_READONLY)
async def tag_list(
    query: Annotated[
        str | None,
        Field(description="Optional substring to filter tag names by."),
    ] = None,
    all_fields: Annotated[
        bool,
        Field(description="If true, return full tag objects instead of names only."),
    ] = False,
) -> list[Any]:
    """List tags used across the catalogue, optionally filtered by substring."""
    return await call_action(
        "tag_list", {"query": query, "all_fields": all_fields}
    )


@mcp.tool(annotations=_READONLY)
async def tag_show(
    id: Annotated[str, Field(description="Tag name or id.")],
    include_datasets: Annotated[
        bool,
        Field(description="If true, include the datasets carrying this tag."),
    ] = False,
) -> dict[str, Any]:
    """Get details for a single tag, optionally with the datasets that use it."""
    return await call_action(
        "tag_show", {"id": id, "include_datasets": include_datasets}
    )


@mcp.tool(annotations=_READONLY)
async def organization_list(
    limit: Annotated[
        int, Field(ge=1, le=1000, description="Max organizations to return.")
    ] = 100,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
    all_fields: Annotated[
        bool,
        Field(description="If true, return full org objects instead of names only."),
    ] = False,
) -> list[Any]:
    """List the organizations (data publishers) in the catalogue.

    Useful for building an 'organization:<name>' filter for package_search.
    """
    return await call_action(
        "organization_list",
        {"limit": limit, "offset": offset, "all_fields": all_fields},
    )


@mcp.tool(annotations=_READONLY)
async def group_list(
    limit: Annotated[
        int, Field(ge=1, le=1000, description="Max groups to return.")
    ] = 100,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
    all_fields: Annotated[
        bool,
        Field(description="If true, return full group objects instead of names only."),
    ] = False,
) -> list[Any]:
    """List the groups (themes / categories) in the catalogue.

    Useful for building a 'groups:<name>' filter for package_search.
    """
    return await call_action(
        "group_list",
        {"limit": limit, "offset": offset, "all_fields": all_fields},
    )


def main() -> None:
    """Console-script entry point. Defaults to stdio; set MCP_TRANSPORT=http for HTTP."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(
            transport="http",
            host=os.environ.get("MCP_HOST", "127.0.0.1"),
            port=int(os.environ.get("MCP_PORT", "8000")),
        )
    else:
        mcp.run()


if __name__ == "__main__":
    main()
