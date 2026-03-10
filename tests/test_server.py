"""
Tests for mcp-bring server tools.

Uses mocking to avoid real Bring! API calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_bring():
    """Create a mocked Bring API instance."""
    bring = MagicMock()
    bring.login = AsyncMock()
    bring.load_lists = AsyncMock(return_value={
        "lists": [
            {"listUuid": "list-123", "name": "Grocery", "theme": "ch.publisheria.bring.theme.green"},
            {"listUuid": "list-456", "name": "Hardware Store", "theme": "ch.publisheria.bring.theme.blue"},
        ]
    })
    bring.get_list = AsyncMock(return_value={
        "purchase": [
            {"name": "Milk", "specification": "2L"},
            {"name": "Eggs", "specification": ""},
        ],
        "recently": [
            {"name": "Butter", "specification": ""},
        ]
    })
    bring.get_all_item_details = AsyncMock(return_value=[
        {
            "uuid": "item-001",
            "itemId": "Milk",
            "specification": "2L",
            "attributes": [{"type": "SectionCategory", "value": "Dairy"}],
        },
        {
            "uuid": "item-002",
            "itemId": "Eggs",
            "specification": "",
            "attributes": [],
        },
    ])
    bring.get_lists_users = AsyncMock(return_value=[
        {"publicUuid": "user-001", "name": "Alex", "email": "alex@example.com"},
        {"publicUuid": "user-002", "name": "Babsi", "email": "babsi@example.com"},
    ])
    bring.get_activity = AsyncMock(return_value={
        "timeline": [
            {"type": "ITEM_ADDED", "itemId": "Milk", "userId": "user-001", "timestamp": 1700000000},
            {"type": "ITEM_COMPLETED", "itemId": "Butter", "userId": "user-002", "timestamp": 1700001000},
        ]
    })
    bring.save_item = AsyncMock()
    bring.remove_item = AsyncMock()
    bring.complete_item = AsyncMock()
    bring.update_item = AsyncMock()
    bring.batch_update_list = AsyncMock()
    bring.get_user_account = AsyncMock(return_value={
        "email": "test@example.com",
        "name": "Test User",
        "publicUuid": "user-uuid-123",
    })
    return bring


@pytest.fixture
def mock_ctx(mock_bring):
    """Create a mocked FastMCP context with bring instance."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"bring": mock_bring}
    return ctx


# ---------------------------------------------------------------------------
# Tests — get_lists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_lists_returns_list(mock_ctx, mock_bring):
    """get_lists should return the list of shopping lists."""
    from mcp_bring.server import get_lists

    result = await get_lists(mock_ctx)

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["listUuid"] == "list-123"
    assert result[0]["name"] == "Grocery"
    mock_bring.load_lists.assert_called_once()


@pytest.mark.asyncio
async def test_get_lists_empty(mock_ctx, mock_bring):
    """get_lists should handle an empty lists response."""
    from mcp_bring.server import get_lists

    mock_bring.load_lists.return_value = {"lists": []}
    result = await get_lists(mock_ctx)

    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_lists_request_error(mock_ctx, mock_bring):
    """get_lists should raise ToolError on BringRequestException."""
    from mcp_bring.server import get_lists
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.load_lists.side_effect = BringRequestException("Network error")

    with pytest.raises(ToolError, match="API request failed"):
        await get_lists(mock_ctx)


# ---------------------------------------------------------------------------
# Tests — get_list_items
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_list_items_returns_purchase_and_recently(mock_ctx, mock_bring):
    """get_list_items should return both 'purchase' and 'recently' sections."""
    from mcp_bring.server import get_list_items

    result = await get_list_items(mock_ctx, list_uuid="list-123")

    assert "purchase" in result
    assert "recently" in result
    assert len(result["purchase"]) == 2
    assert result["purchase"][0]["name"] == "Milk"
    mock_bring.get_list.assert_called_once_with("list-123")


@pytest.mark.asyncio
async def test_get_list_items_correct_uuid(mock_ctx, mock_bring):
    """get_list_items should pass the list_uuid to bring.get_list."""
    from mcp_bring.server import get_list_items

    await get_list_items(mock_ctx, list_uuid="list-456")

    mock_bring.get_list.assert_called_once_with("list-456")


@pytest.mark.asyncio
async def test_get_list_items_error(mock_ctx, mock_bring):
    """get_list_items should raise ToolError on API failure."""
    from mcp_bring.server import get_list_items
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.get_list.side_effect = BringRequestException("Not found")

    with pytest.raises(ToolError):
        await get_list_items(mock_ctx, list_uuid="bad-uuid")


# ---------------------------------------------------------------------------
# Tests — get_list_details
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_list_details_returns_item_list(mock_ctx, mock_bring):
    """get_list_details should return detailed item info."""
    from mcp_bring.server import get_list_details

    result = await get_list_details(mock_ctx, list_uuid="list-123")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["itemId"] == "Milk"
    mock_bring.get_all_item_details.assert_called_once_with("list-123")


@pytest.mark.asyncio
async def test_get_list_details_error(mock_ctx, mock_bring):
    """get_list_details should raise ToolError on failure."""
    from mcp_bring.server import get_list_details
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.get_all_item_details.side_effect = BringRequestException("Oops")

    with pytest.raises(ToolError):
        await get_list_details(mock_ctx, list_uuid="list-123")


# ---------------------------------------------------------------------------
# Tests — get_list_users
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_list_users_returns_user_list(mock_ctx, mock_bring):
    """get_list_users should return all users sharing a list."""
    from mcp_bring.server import get_list_users

    result = await get_list_users(mock_ctx, list_uuid="list-123")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["name"] == "Alex"
    mock_bring.get_lists_users.assert_called_once_with("list-123")


@pytest.mark.asyncio
async def test_get_list_users_error(mock_ctx, mock_bring):
    """get_list_users should raise ToolError on failure."""
    from mcp_bring.server import get_list_users
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.get_lists_users.side_effect = BringRequestException("Forbidden")

    with pytest.raises(ToolError):
        await get_list_users(mock_ctx, list_uuid="list-123")


# ---------------------------------------------------------------------------
# Tests — get_list_activity
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_list_activity_returns_timeline(mock_ctx, mock_bring):
    """get_list_activity should return activity data."""
    from mcp_bring.server import get_list_activity

    result = await get_list_activity(mock_ctx, list_uuid="list-123")

    assert "timeline" in result
    assert len(result["timeline"]) == 2
    mock_bring.get_activity.assert_called_once_with("list-123")


@pytest.mark.asyncio
async def test_get_list_activity_error(mock_ctx, mock_bring):
    """get_list_activity should raise ToolError on failure."""
    from mcp_bring.server import get_list_activity
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.get_activity.side_effect = BringRequestException("Server error")

    with pytest.raises(ToolError):
        await get_list_activity(mock_ctx, list_uuid="list-123")


# ---------------------------------------------------------------------------
# Tests — add_item
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_item_calls_save_item(mock_ctx, mock_bring):
    """add_item should call bring.save_item with correct args."""
    from mcp_bring.server import add_item

    result = await add_item(mock_ctx, list_uuid="list-123", item_name="Oat Milk", spec="2L")

    mock_bring.save_item.assert_called_once_with("list-123", "Oat Milk", "2L")
    assert result["status"] == "added"
    assert result["item"] == "Oat Milk"
    assert result["spec"] == "2L"
    assert result["list_uuid"] == "list-123"


@pytest.mark.asyncio
async def test_add_item_without_spec(mock_ctx, mock_bring):
    """add_item should work with no spec provided."""
    from mcp_bring.server import add_item

    result = await add_item(mock_ctx, list_uuid="list-123", item_name="Eggs")

    mock_bring.save_item.assert_called_once_with("list-123", "Eggs", "")
    assert result["status"] == "added"


@pytest.mark.asyncio
async def test_add_item_auth_error(mock_ctx, mock_bring):
    """add_item should raise ToolError on BringAuthException."""
    from mcp_bring.server import add_item
    from bring_api.exceptions import BringAuthException
    from fastmcp.exceptions import ToolError

    mock_bring.save_item.side_effect = BringAuthException("Token expired")

    with pytest.raises(ToolError, match="Authentication failed"):
        await add_item(mock_ctx, list_uuid="list-123", item_name="Milk")


@pytest.mark.asyncio
async def test_add_item_request_error(mock_ctx, mock_bring):
    """add_item should raise ToolError on BringRequestException."""
    from mcp_bring.server import add_item
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.save_item.side_effect = BringRequestException("Server 500")

    with pytest.raises(ToolError, match="API request failed"):
        await add_item(mock_ctx, list_uuid="list-123", item_name="Milk")


# ---------------------------------------------------------------------------
# Tests — add_items (batch)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_items_batch(mock_ctx, mock_bring):
    """add_items should call batch_update_list with ADD operation."""
    from mcp_bring.server import add_items
    from bring_api.types import BringItemOperation

    items = [
        {"name": "Milk", "spec": "2L"},
        {"name": "Eggs"},
        {"name": "Butter", "spec": "organic"},
    ]

    result = await add_items(mock_ctx, list_uuid="list-123", items=items)

    mock_bring.batch_update_list.assert_called_once()
    call_args = mock_bring.batch_update_list.call_args
    assert call_args[0][0] == "list-123"
    assert call_args[0][2] == BringItemOperation.ADD
    assert result["count"] == 3
    assert "Milk" in result["items"]
    assert result["status"] == "added"


@pytest.mark.asyncio
async def test_add_items_sends_correct_format(mock_ctx, mock_bring):
    """add_items should convert items to bring-api format."""
    from mcp_bring.server import add_items

    items = [{"name": "Tomatoes", "spec": "500g"}, {"name": "Pasta"}]
    await add_items(mock_ctx, list_uuid="list-123", items=items)

    call_args = mock_bring.batch_update_list.call_args
    bring_items = call_args[0][1]
    assert bring_items[0]["itemId"] == "Tomatoes"
    assert bring_items[0]["spec"] == "500g"
    assert bring_items[1]["itemId"] == "Pasta"
    assert bring_items[1]["spec"] == ""


@pytest.mark.asyncio
async def test_add_items_error(mock_ctx, mock_bring):
    """add_items should raise ToolError on failure."""
    from mcp_bring.server import add_items
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.batch_update_list.side_effect = BringRequestException("Batch failed")

    with pytest.raises(ToolError):
        await add_items(mock_ctx, list_uuid="list-123", items=[{"name": "Milk"}])


# ---------------------------------------------------------------------------
# Tests — complete_item
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_complete_item(mock_ctx, mock_bring):
    """complete_item should call bring.complete_item."""
    from mcp_bring.server import complete_item

    result = await complete_item(mock_ctx, list_uuid="list-123", item_name="Milk")

    mock_bring.complete_item.assert_called_once_with("list-123", "Milk")
    assert result["status"] == "completed"
    assert result["item"] == "Milk"
    assert result["list_uuid"] == "list-123"


@pytest.mark.asyncio
async def test_complete_item_error(mock_ctx, mock_bring):
    """complete_item should raise ToolError on failure."""
    from mcp_bring.server import complete_item
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.complete_item.side_effect = BringRequestException("Item not found")

    with pytest.raises(ToolError):
        await complete_item(mock_ctx, list_uuid="list-123", item_name="Ghost Item")


# ---------------------------------------------------------------------------
# Tests — remove_item
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remove_item(mock_ctx, mock_bring):
    """remove_item should call bring.remove_item."""
    from mcp_bring.server import remove_item

    result = await remove_item(mock_ctx, list_uuid="list-123", item_name="Butter")

    mock_bring.remove_item.assert_called_once_with("list-123", "Butter")
    assert result["status"] == "removed"
    assert result["item"] == "Butter"
    assert result["list_uuid"] == "list-123"


@pytest.mark.asyncio
async def test_remove_item_error(mock_ctx, mock_bring):
    """remove_item should raise ToolError on failure."""
    from mcp_bring.server import remove_item
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.remove_item.side_effect = BringRequestException("Delete failed")

    with pytest.raises(ToolError):
        await remove_item(mock_ctx, list_uuid="list-123", item_name="Butter")


# ---------------------------------------------------------------------------
# Tests — update_item_spec
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_item_spec(mock_ctx, mock_bring):
    """update_item_spec should call bring.update_item with new spec."""
    from mcp_bring.server import update_item_spec

    result = await update_item_spec(
        mock_ctx, list_uuid="list-123", item_name="Milk", spec="1L, oat"
    )

    mock_bring.update_item.assert_called_once_with("list-123", "Milk", "1L, oat")
    assert result["status"] == "updated"
    assert result["item"] == "Milk"
    assert result["spec"] == "1L, oat"
    assert result["list_uuid"] == "list-123"


@pytest.mark.asyncio
async def test_update_item_spec_empty(mock_ctx, mock_bring):
    """update_item_spec should allow clearing a spec."""
    from mcp_bring.server import update_item_spec

    result = await update_item_spec(mock_ctx, list_uuid="list-123", item_name="Eggs", spec="")

    mock_bring.update_item.assert_called_once_with("list-123", "Eggs", "")
    assert result["spec"] == ""


@pytest.mark.asyncio
async def test_update_item_spec_error(mock_ctx, mock_bring):
    """update_item_spec should raise ToolError on failure."""
    from mcp_bring.server import update_item_spec
    from bring_api.exceptions import BringAuthException
    from fastmcp.exceptions import ToolError

    mock_bring.update_item.side_effect = BringAuthException("Session expired")

    with pytest.raises(ToolError, match="Authentication failed"):
        await update_item_spec(mock_ctx, list_uuid="list-123", item_name="Milk", spec="2L")


# ---------------------------------------------------------------------------
# Tests — get_account_info
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_account_info(mock_ctx, mock_bring):
    """get_account_info should return user account data."""
    from mcp_bring.server import get_account_info

    result = await get_account_info(mock_ctx)

    mock_bring.get_user_account.assert_called_once()
    assert result["email"] == "test@example.com"
    assert result["name"] == "Test User"
    assert result["publicUuid"] == "user-uuid-123"


@pytest.mark.asyncio
async def test_get_account_info_error(mock_ctx, mock_bring):
    """get_account_info should raise ToolError on failure."""
    from mcp_bring.server import get_account_info
    from bring_api.exceptions import BringRequestException
    from fastmcp.exceptions import ToolError

    mock_bring.get_user_account.side_effect = BringRequestException("Unauthorized")

    with pytest.raises(ToolError):
        await get_account_info(mock_ctx)


# ---------------------------------------------------------------------------
# Tests — Error handling (generic/unexpected)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unexpected_error_wrapped_in_tool_error(mock_ctx, mock_bring):
    """Unexpected errors should be wrapped in ToolError."""
    from mcp_bring.server import get_lists
    from fastmcp.exceptions import ToolError

    mock_bring.load_lists.side_effect = RuntimeError("Something totally unexpected")

    with pytest.raises(ToolError, match="Unexpected error"):
        await get_lists(mock_ctx)


# ---------------------------------------------------------------------------
# Tests — Allowlist feature
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ctx_with_allowlist(mock_bring):
    """Create a mocked context with allowlist set to only list-123."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {
        "bring": mock_bring,
        "allowed_list_uuids": {"list-123"},
    }
    return ctx


@pytest.mark.asyncio
async def test_get_lists_filtered_by_allowlist(mock_ctx_with_allowlist, mock_bring):
    """get_lists should only return lists that are in the allowlist."""
    from mcp_bring.server import get_lists

    result = await get_lists(mock_ctx_with_allowlist)

    # Only list-123 is in the allowlist; list-456 should be filtered out
    assert len(result) == 1
    assert result[0]["listUuid"] == "list-123"


@pytest.mark.asyncio
async def test_get_list_items_blocked_by_allowlist(mock_ctx_with_allowlist, mock_bring):
    """get_list_items should raise ToolError for a list not in the allowlist."""
    from mcp_bring.server import get_list_items
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="not in the configured allowlist"):
        await get_list_items(mock_ctx_with_allowlist, list_uuid="list-456")


@pytest.mark.asyncio
async def test_get_list_items_allowed_by_allowlist(mock_ctx_with_allowlist, mock_bring):
    """get_list_items should succeed for a list in the allowlist."""
    from mcp_bring.server import get_list_items

    result = await get_list_items(mock_ctx_with_allowlist, list_uuid="list-123")

    assert "purchase" in result
    mock_bring.get_list.assert_called_once_with("list-123")


@pytest.mark.asyncio
async def test_add_item_blocked_by_allowlist(mock_ctx_with_allowlist, mock_bring):
    """add_item should raise ToolError for a list not in the allowlist."""
    from mcp_bring.server import add_item
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="not in the configured allowlist"):
        await add_item(mock_ctx_with_allowlist, list_uuid="list-456", item_name="Milk")

    mock_bring.save_item.assert_not_called()


@pytest.mark.asyncio
async def test_remove_item_blocked_by_allowlist(mock_ctx_with_allowlist, mock_bring):
    """remove_item should raise ToolError for a list not in the allowlist."""
    from mcp_bring.server import remove_item
    from fastmcp.exceptions import ToolError

    with pytest.raises(ToolError, match="not in the configured allowlist"):
        await remove_item(mock_ctx_with_allowlist, list_uuid="list-456", item_name="Butter")

    mock_bring.remove_item.assert_not_called()


@pytest.mark.asyncio
async def test_no_allowlist_allows_all_lists(mock_ctx, mock_bring):
    """When no allowlist is set (None), all lists should be accessible."""
    from mcp_bring.server import add_item

    # mock_ctx has allowed_list_uuids=None (no allowlist)
    result = await add_item(mock_ctx, list_uuid="list-456", item_name="Hammer")

    assert result["status"] == "added"
    mock_bring.save_item.assert_called_once_with("list-456", "Hammer", "")
