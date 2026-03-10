# PRD: Bring! MCP Server

**Version:** 0.1  
**Status:** Draft  
**Author:** Jarvis (Scout PM)  
**Date:** 2026-03-10

---

## 1. Overview & Goals

### Problem

Bring! is a popular collaborative shopping list app widely used in the DACH region. It has no official API. Claude (and other MCP-compatible AI assistants) cannot interact with Bring! lists today — meaning users can't say "add milk and eggs to the shopping list" and have it actually happen.

### Solution

A **Model Context Protocol (MCP) server** that wraps the unofficial Bring! API, exposing it as a clean set of tools for AI assistants. Users configure it once with their Bring! credentials, and then Claude can read, add, complete, and remove items from their shopping lists directly.

### Primary Use Cases

1. **Voice-to-list:** "Add oat milk, eggs, and avocado to my grocery list"
2. **Meal planning integration:** "Add all ingredients for carbonara to the shopping list"
3. **List review:** "What's on my shopping list right now?"
4. **Completion tracking:** "Mark milk as purchased"
5. **Multi-list management:** "Show me all my Bring! lists"

### Success Criteria

- Claude can list, read, add, complete, and remove items on any Bring! list
- Auth works transparently (no manual token management from the user)
- Compatible with Claude Desktop and any MCP-compatible client
- < 1s response time for typical tool calls

---

## 2. Bring! API — Research Summary

### Authentication

- **Method:** Email + password → Bearer token (JWT)
- **Token lifecycle:** Access token expires periodically; refresh token available
- **Auto-refresh:** The `bring-api` Python library handles token refresh transparently
- **No OAuth:** Credentials must be provided directly (email + password)

### Available Operations (via `miaucl/bring-api` PyPI package)

| Operation | API Method |
|---|---|
| Login | `login()` |
| Refresh token | `retrieve_new_access_token()` |
| List all shopping lists | `load_lists()` |
| Get items in a list | `get_list(list_uuid)` |
| Get detailed item info | `get_all_item_details(list_uuid)` |
| Add item | `save_item(list_uuid, name, spec)` |
| Update item spec | `update_item(list_uuid, name, spec)` |
| Complete/check off item | `complete_item(list_uuid, name)` |
| Remove item | `remove_item(list_uuid, name)` |
| Batch add/complete/remove | `batch_update_list(list_uuid, items, op)` |
| Get current user info | `get_user_account()` |
| Get list users | `get_lists_users(list_uuid)` |
| Get list activity | `get_activity(list_uuid)` |
| Send push notification | `notify(list_uuid, type, item_name)` |
| Get user settings | `get_all_user_settings()` |

### Existing Libraries

- **Python (recommended):** [`bring-api`](https://github.com/miaucl/bring-api) on PyPI — actively maintained (latest 1.1.1, Oct 2025), async-first, used in Home Assistant
- **Node.js:** [`bring-shopping`](https://github.com/foxriver76/node-bring-api) — original reverse-engineering, zero-dependency TypeScript

### Known Limitations / Caveats

- **Unofficial API** — no stability guarantees; could break with Bring! app updates
- **No rate limit documentation** — be conservative, avoid polling
- **Item renaming is fragile** — Bring! app has display bugs with renamed items; avoid
- **Auth is email/password only** — no OAuth, no API key flow; credentials must be stored in env

---

## 3. MCP Tool Design

### Tool List

#### List Management
| Tool | Description | Parameters |
|---|---|---|
| `get_lists` | Get all Bring! shopping lists | — |
| `get_list_items` | Get current + recently-purchased items for a list | `list_uuid` |
| `get_list_details` | Get detailed item info (images, attributes) for a list | `list_uuid` |
| `get_list_users` | Get users sharing a list | `list_uuid` |
| `get_list_activity` | Get recent activity for a list | `list_uuid` |

#### Item Operations
| Tool | Description | Parameters |
|---|---|---|
| `add_item` | Add an item to a list | `list_uuid`, `item_name`, `spec?` |
| `add_items` | Add multiple items at once (batch) | `list_uuid`, `items: [{name, spec?}]` |
| `complete_item` | Mark an item as purchased (moves to "recently purchased") | `list_uuid`, `item_name` |
| `remove_item` | Remove an item from a list entirely | `list_uuid`, `item_name` |
| `update_item_spec` | Update the specification/notes on an item | `list_uuid`, `item_name`, `spec` |

#### User & Account
| Tool | Description | Parameters |
|---|---|---|
| `get_account_info` | Get current user account info | — |

### Resources (read-only, MCP resource protocol)

| URI | Description |
|---|---|
| `bring://lists` | All shopping lists |
| `bring://lists/{list_uuid}/items` | Items in a specific list |

### Notes on Tool Design

- **`get_list_items` is the workhorse** — returns both `purchase` (to-buy) and `recently` (completed/purchased) items
- **`add_items` batch** — uses `batch_update_list` under the hood for efficiency; better for "add 5 ingredients" scenarios
- **`complete_item` vs `remove_item`** — `complete_item` moves to "recently purchased" (still visible, can restore), `remove_item` removes entirely. Both are useful and distinct.
- **No `rename_item` tool** — renaming is explicitly NOT recommended by the API (display bugs in Bring! app); excluded intentionally

---

## 4. Authentication Approach for MCP

### Strategy: Environment Variables

The MCP server reads credentials from environment variables at startup:

```
BRING_EMAIL=alex@example.com
BRING_PASSWORD=secret123
```

Claude Desktop config (`claude_desktop_config.json`) passes these via `env`:

```json
{
  "mcpServers": {
    "bring": {
      "command": "uv",
      "args": ["run", "mcp-bring"],
      "env": {
        "BRING_EMAIL": "alex@example.com",
        "BRING_PASSWORD": "your_password"
      }
    }
  }
}
```

### Session Management

- Single `aiohttp.ClientSession` + `Bring` instance created at server startup
- `bring-api` handles token refresh automatically
- Session is shared across all tool calls (no re-login per call)
- On auth failure, raise a descriptive `ToolError`

---

## 5. Stack Recommendation

| Decision | Choice | Rationale |
|---|---|---|
| Language | **Python** | `bring-api` library exists and is well-maintained; aligns with Alex's FastMCP preference |
| MCP Framework | **FastMCP** (standalone, `pip install fastmcp`) | Clean decorator-based API, handles all protocol boilerplate |
| Transport | **stdio** | Standard for Claude Desktop; no network config needed |
| HTTP Client | **aiohttp** | Required by `bring-api`; async-native |
| Package Manager | **uv** | Fast, modern; works great with Claude Desktop |
| Python Version | **3.12+** | Required by `bring-api` ≥ 0.6.0 |

**Not recommended:**
- TypeScript/Node.js: The Node bring-api is the original but less maintained; Python ecosystem is better here
- Custom HTTP calls: The `bring-api` library is solid, no need to reinvent

---

## 6. List Allowlist

### Feature: `BRING_LIST_ALLOWLIST`

Users may want to restrict the MCP server to only a subset of their Bring! lists — for example, exposing only the household grocery list to Claude, not personal wishlists.

**Requirements:**

- The server supports an optional `BRING_LIST_ALLOWLIST` environment variable
- Value is a comma-separated list of list **names** or **UUIDs** (or a mix)
- When set, **all tools** that return or operate on lists must filter to only the allowed lists:
  - `get_lists` — returns only allowed lists
  - `get_list_items`, `get_list_details`, `get_list_users`, `get_list_activity` — raise `ToolError` if the requested `list_uuid` is not allowed
  - `add_item`, `add_items`, `complete_item`, `remove_item`, `update_item_spec` — raise `ToolError` if the target `list_uuid` is not allowed
- When unset or empty, all lists are accessible — **no breaking change** to default behaviour
- The allowlist is resolved **once at startup** (during lifespan): list names are looked up and converted to a set of UUIDs, stored in the lifespan context
- A clear `ToolError` message is returned when access to a non-allowed list is attempted

**Configuration example:**

```
# By name:
BRING_LIST_ALLOWLIST=Groceries,Hardware Store

# By UUID:
BRING_LIST_ALLOWLIST=a1b2c3d4-e5f6-7890-abcd-ef1234567890

# Mix of both:
BRING_LIST_ALLOWLIST=Groceries,a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

---

## 7. Non-Goals (v1)

- No webhook/push notification support (not feasible with MCP stdio)
- No list creation/deletion (API supports it, but out of scope for v1)
- No image/photo handling for items
- No user invitation/sharing management
- No multi-account support

---

## 8. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bring! changes their API | Medium | Pin `bring-api` version; monitor upstream repo |
| Credentials in env vars | Low risk for local use | Document clearly; no cloud deployment in v1 |
| Token expiry mid-session | Low | `bring-api` handles auto-refresh |
| Rate limiting | Unknown | Don't poll; only call on demand |
