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
        str,
        Field(
            description=(
                "Solr search query. Free text ('housing dublin'), a quoted "
                "phrase ('\"electric vehicles\"'), or a fielded query "
                "('title:census'). Defaults to '*:*' (match everything)."
            )
        ),
    ] = "*:*",
    rows: Annotated[
        int, Field(ge=1, le=100, description="Max datasets to return per page (1-100).")
    ] = 10,
    start: Annotated[
        int,
        Field(
            ge=0,
            description=(
                "Offset into the result set, for paging; use with rows "
                "(e.g. rows=10, start=10 for page 2)."
            ),
        ),
    ] = 0,
    fq: Annotated[
        str | None,
        Field(
            description=(
                "CKAN facet filter query; space-separate several to AND them. "
                "Examples: 'organization:central-statistics-office', "
                "'res_format:CSV', 'groups:housing', 'tags:covid-19'. Get valid "
                "values from organization_list, group_list and tag_list."
            )
        ),
    ] = None,
    sort: Annotated[
        str | None,
        Field(
            description=(
                "Solr sort order as 'field direction'. Examples: 'score desc' "
                "(relevance), 'metadata_modified desc' (most recently updated), "
                "'title_string asc'."
            )
        ),
    ] = None,
) -> dict[str, Any]:
    """Search the data.gov.ie dataset catalogue — the primary discovery tool.

    Start here whenever you're looking for data. Returns `count` (total matches)
    and a `results` list of full dataset metadata (title, notes, organization,
    tags, groups, and each dataset's resources with download URLs).

    Use `q` for Solr free-text/fielded search and `fq` to filter by facet
    (organization, groups, tags, res_format). Page large result sets with
    `rows` + `start`. Follow up with package_show on a result's `name` for the
    complete record.
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
                "Dataset name (slug) or id from a package_search result, "
                "e.g. 'the-walled-towns-of-ireland'."
            )
        ),
    ],
) -> dict[str, Any]:
    """Get the full record for one dataset, including all of its resources.

    Returns complete metadata (title, description, publisher organization, tags,
    groups, licence, temporal/spatial coverage) plus a `resources` list. Each
    resource carries a download `url` and `format` (CSV, JSON, XLSX, GeoJSON,
    API, …); resources with `datastore_active: true` are additionally queryable.
    Look the dataset up via package_search first and pass its `name` here.
    """
    return await call_action("package_show", {"id": id})


@mcp.tool(annotations=_READONLY)
async def package_list(
    limit: Annotated[
        int, Field(ge=1, le=1000, description="Max dataset names to return.")
    ] = 100,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
) -> list[str]:
    """List raw dataset names (slugs) in the catalogue, paged.

    Returns just the slugs — no metadata. The catalogue holds 20,000+ datasets,
    so this is rarely what you want: prefer package_search whenever you have any
    notion of the topic, publisher or format. Use this only to enumerate or
    count the entire catalogue.
    """
    return await call_action("package_list", {"limit": limit, "offset": offset})


@mcp.tool(annotations=_READONLY)
async def resource_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Field-scoped query of the form 'field:term'. Searchable fields "
                "include name, description, format and url — e.g. 'format:CSV', "
                "'name:census', 'name:Walled Towns'. Plain text without a "
                "'field:' prefix will not match."
            )
        ),
    ],
    limit: Annotated[
        int, Field(ge=1, le=100, description="Max resources to return.")
    ] = 10,
    offset: Annotated[int, Field(ge=0, description="Offset for paging.")] = 0,
) -> dict[str, Any]:
    """Search individual resources (files / API endpoints) across all datasets.

    Use when you want a specific file rather than a whole dataset. Returns
    `count` and a `results` list of resource objects, each with a download
    `url`, `format`, `name`/`description` and parent `package_id` (pass that to
    package_show for the owning dataset).
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
    """List tags used across the catalogue, optionally filtered by substring.

    Returns tag names (or full tag objects when all_fields=True). The names
    double as valid values for package_search's `fq` filter as 'tags:<name>'.
    """
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
    """Get details for a single tag, optionally with the datasets that carry it.

    With include_datasets=True the response embeds the tagged datasets, making
    this a quick way to browse everything filed under one tag.
    """
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

    Returns publisher slugs (or full objects with titles and dataset counts
    when all_fields=True). Use a slug to build an 'organization:<slug>' `fq`
    filter for package_search (e.g. 'central-statistics-office').
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

    Returns group slugs (or full objects when all_fields=True). Use a slug to
    build a 'groups:<slug>' `fq` filter for package_search.
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
