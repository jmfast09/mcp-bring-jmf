"""
Bring! MCP Server

Exposes the unofficial Bring! shopping list API as MCP tools for Claude and
other MCP-compatible AI assistants.

Auth: Set BRING_EMAIL and BRING_PASSWORD environment variables.
"""

import logging
import os
import asyncio
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

import aiohttp
from bring_api import Bring
from bring_api.exceptions import BringAuthException, BringRequestException
from bring_api.types import BringItemOperation
from fastmcp import FastMCP, Context
from fastmcp.exceptions import ToolError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Server lifespan — create shared Bring session once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize and tear down the Bring! API session."""
    email = os.environ.get("BRING_EMAIL")
    password = os.environ.get("BRING_PASSWORD")

    if not email or not password:
        raise RuntimeError(
            "Missing Bring! credentials. Set BRING_EMAIL and BRING_PASSWORD "
            "environment variables."
        )

    async with aiohttp.ClientSession() as session:
        bring = Bring(session, email, password)
        try:
            await bring.login()
        except BringAuthException as e:
            raise RuntimeError(
                f"Failed to authenticate with Bring!: {e}. "
                "Check your BRING_EMAIL and BRING_PASSWORD."
            ) from e

        # ---------------------------------------------------------------------------
        # Allowlist — resolve names/UUIDs to a set of permitted list UUIDs
        # ---------------------------------------------------------------------------
        raw_allowlist = os.environ.get("BRING_LIST_ALLOWLIST", "").strip()
        allowed_list_uuids: set[str] | None = None

        if raw_allowlist:
            allowlist_entries = {s.strip() for s in raw_allowlist.split(",") if s.strip()}
            if allowlist_entries:
                all_lists_result = await bring.load_lists()
                allowed_list_uuids = {
                    lst.listUuid
                    for lst in all_lists_result.lists
                    if lst.listUuid in allowlist_entries
                    or lst.name in allowlist_entries
                }

        yield {"bring": bring, "allowed_list_uuids": allowed_list_uuids}


# ---------------------------------------------------------------------------
# FastMCP server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="Bring! Shopping Lists",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bring(ctx: Context) -> Bring:
    """Extract Bring instance from FastMCP context."""
    return ctx.request_context.lifespan_context["bring"]


def _allowed_uuids(ctx: Context) -> set[str] | None:
    """Return the set of allowed list UUIDs, or None if no allowlist is configured."""
    return ctx.request_context.lifespan_context.get("allowed_list_uuids")


def _check_list_allowed(ctx: Context, list_uuid: str) -> None:
    """Raise ToolError if list_uuid is not permitted by the allowlist."""
    allowed = _allowed_uuids(ctx)
    if allowed is not None and list_uuid not in allowed:
        raise ToolError(
            f"List '{list_uuid}' is not in the configured allowlist. "
            "Check your BRING_LIST_ALLOWLIST setting."
        )


def _handle_error(e: Exception, action: str) -> None:
    """Convert bring-api exceptions to ToolErrors."""
    if isinstance(e, BringAuthException):
        raise ToolError(
            f"Authentication failed while {action}. "
            "Your session may have expired. Restart the MCP server."
        ) from e
    if isinstance(e, BringRequestException):
        raise ToolError(f"Bring! API request failed while {action}: {e}") from e
    raise ToolError(f"Unexpected error while {action}: {e}") from e


# ---------------------------------------------------------------------------
# Tools — List Management
# ---------------------------------------------------------------------------

@mcp.tool
async def get_lists(ctx: Context) -> list[dict[str, Any]]:
    """
    Get all Bring! shopping lists for the logged-in user.

    Returns a list of lists with their uuid, name, and theme.
    Use the listUuid from this response in other tools.
    """
    bring = _bring(ctx)
    try:
        result = await bring.load_lists()
        lists = result.lists
        allowed = _allowed_uuids(ctx)
        if allowed is not None:
            lists = [lst for lst in lists if lst.listUuid in allowed]
        return [lst.to_dict() for lst in lists]
    except Exception as e:
        _handle_error(e, "fetching lists")


@mcp.tool
async def get_list_items(ctx: Context, list_uuid: str) -> dict[str, Any]:
    """
    Get the current items in a Bring! shopping list.

    Returns two groups:
    - 'purchase': items still to buy
    - 'recently': items recently purchased/completed

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        result = await bring.get_list(list_uuid)
        return {
            "purchase": [i.to_dict() for i in result.items.purchase],
            "recently": [i.to_dict() for i in result.items.recently],
        }
    except Exception as e:
        _handle_error(e, f"fetching items for list {list_uuid}")


@mcp.tool
async def get_list_details(ctx: Context, list_uuid: str) -> list[dict[str, Any]]:
    """
    Get detailed information about items in a Bring! shopping list,
    including item attributes, images, and metadata.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        result = await bring.get_all_item_details(list_uuid)
        return [item.to_dict() for item in result.items]
    except Exception as e:
        _handle_error(e, f"fetching item details for list {list_uuid}")


@mcp.tool
async def get_list_users(ctx: Context, list_uuid: str) -> list[dict[str, Any]]:
    """
    Get users who share a Bring! shopping list.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        result = await bring.get_lists_users(list_uuid)
        return [asdict(u) for u in result.users]
    except Exception as e:
        _handle_error(e, f"fetching users for list {list_uuid}")


@mcp.tool
async def get_list_activity(ctx: Context, list_uuid: str) -> dict[str, Any]:
    """
    Get recent activity for a Bring! shopping list (who added/removed what).

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        result = await bring.get_activity(list_uuid)
        return result.to_dict()
    except Exception as e:
        _handle_error(e, f"fetching activity for list {list_uuid}")


# ---------------------------------------------------------------------------
# Tools — Item Operations
# ---------------------------------------------------------------------------

@mcp.tool
async def add_item(
    ctx: Context,
    list_uuid: str,
    item_name: str,
    spec: str = "",
) -> dict[str, str]:
    """
    Add a single item to a Bring! shopping list.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
        item_name: Name of the item to add (e.g. "Milk", "Oat milk", "Eggs")
        spec: Optional specification or note (e.g. "2L", "organic", "low fat")

    Returns:
        Confirmation with the item name and list.
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        await bring.save_item(list_uuid, item_name, spec)
        return {
            "status": "added",
            "item": item_name,
            "spec": spec,
            "list_uuid": list_uuid,
        }
    except Exception as e:
        _handle_error(e, f"adding item '{item_name}'")


@mcp.tool
async def add_items(
    ctx: Context,
    list_uuid: str,
    items: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Add multiple items to a Bring! shopping list at once.

    This is more efficient than calling add_item repeatedly.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
        items: List of items to add. Each item is a dict with:
               - 'name' (required): item name e.g. "Milk"
               - 'spec' (optional): specification e.g. "2L, organic"

    Example:
        items = [
            {"name": "Milk", "spec": "2L"},
            {"name": "Eggs", "spec": "free range"},
            {"name": "Butter"}
        ]
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)

    # Convert to bring-api format
    bring_items = [
        {
            "itemId": item["name"],
            "spec": item.get("spec", ""),
        }
        for item in items
    ]

    try:
        await bring.batch_update_list(
            list_uuid,
            bring_items,
            BringItemOperation.ADD,
        )
        return {
            "status": "added",
            "count": len(items),
            "items": [item["name"] for item in items],
            "list_uuid": list_uuid,
        }
    except Exception as e:
        _handle_error(e, f"batch adding {len(items)} items")


@mcp.tool
async def complete_item(
    ctx: Context,
    list_uuid: str,
    item_name: str,
) -> dict[str, str]:
    """
    Mark an item as purchased/completed on a Bring! shopping list.

    This moves the item from the active "to buy" section to the
    "recently purchased" section. It does NOT remove it entirely.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
        item_name: Name of the item to mark as purchased
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        await bring.complete_item(list_uuid, item_name)
        return {
            "status": "completed",
            "item": item_name,
            "list_uuid": list_uuid,
        }
    except Exception as e:
        _handle_error(e, f"completing item '{item_name}'")


@mcp.tool
async def remove_item(
    ctx: Context,
    list_uuid: str,
    item_name: str,
) -> dict[str, str]:
    """
    Remove an item from a Bring! shopping list entirely.

    Unlike complete_item, this removes the item completely (not just to
    the "recently purchased" section).

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
        item_name: Name of the item to remove
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        await bring.remove_item(list_uuid, item_name)
        return {
            "status": "removed",
            "item": item_name,
            "list_uuid": list_uuid,
        }
    except Exception as e:
        _handle_error(e, f"removing item '{item_name}'")


@mcp.tool
async def update_item_spec(
    ctx: Context,
    list_uuid: str,
    item_name: str,
    spec: str,
) -> dict[str, str]:
    """
    Update the specification/note on an existing item in a Bring! list.

    Use this to add or change details like quantity, brand, or notes.

    Args:
        list_uuid: The UUID of the shopping list (from get_lists)
        item_name: Name of the item to update
        spec: New specification (e.g. "3 packs", "organic", "from Migros")
    """
    _check_list_allowed(ctx, list_uuid)
    bring = _bring(ctx)
    try:
        await bring.update_item(list_uuid, item_name, spec)
        return {
            "status": "updated",
            "item": item_name,
            "spec": spec,
            "list_uuid": list_uuid,
        }
    except Exception as e:
        _handle_error(e, f"updating spec for item '{item_name}'")


# ---------------------------------------------------------------------------
# Tools — Account
# ---------------------------------------------------------------------------

@mcp.tool
async def get_account_info(ctx: Context) -> dict[str, Any]:
    """
    Get information about the currently logged-in Bring! account.

    Returns name, email, and user UUID.
    """
    bring = _bring(ctx)
    try:
        result = await bring.get_user_account()
        return result.to_dict()
    except Exception as e:
        _handle_error(e, "fetching account info")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    """Entry point for the mcp-bring CLI.

    Transport, host, and port are configured via FastMCP native env vars
    (read automatically by FastMCP 3.x via pydantic-settings):
      FASTMCP_TRANSPORT  (default: streamable-http)
      FASTMCP_HOST       (default: 0.0.0.0)
      FASTMCP_PORT       (default: 8000)
    """
    mcp.run(stateless_http=True)


if __name__ == "__main__":
    main()
