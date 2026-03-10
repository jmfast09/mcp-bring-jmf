# Architecture Decision Record: mcp-bring

**Date:** 2026-03-10  
**Status:** Accepted

---

## Context

Building an MCP server for the Bring! shopping list app. The Bring! API is unofficial (reverse-engineered) with no official documentation. A Python library `bring-api` (miaucl/bring-api on PyPI) exists and is actively maintained (~44 releases, used in Home Assistant).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Desktop                        │
│                (or any MCP-compatible client)            │
└─────────────────────┬───────────────────────────────────┘
                      │ stdio (JSON-RPC)
                      ▼
┌─────────────────────────────────────────────────────────┐
│                  mcp-bring (FastMCP)                     │
│                                                          │
│  ┌──────────────┐    ┌──────────────────────────────┐   │
│  │  Tool Layer  │    │    Auth/Session Manager       │   │
│  │              │    │                               │   │
│  │ @mcp.tool    │───▶│  Bring(session, email, pwd)   │   │
│  │ get_lists    │    │  · auto token refresh         │   │
│  │ get_items    │    │  · single aiohttp session     │   │
│  │ add_item     │    └──────────────┬────────────────┘   │
│  │ complete     │                   │                    │
│  │ remove       │                   │                    │
│  │ ...          │                   │                    │
│  └──────────────┘                   │                    │
└────────────────────────────────────-│────────────────────┘
                                      │ HTTPS
                                      ▼
                         ┌────────────────────────┐
                         │  api.getbring.com/rest/ │
                         │  (Unofficial Bring! API) │
                         └────────────────────────┘
```

---

## Key Decisions

### ADR-1: FastMCP over raw MCP SDK

**Decision:** Use `fastmcp` (standalone package, not `mcp[cli]`)

**Rationale:**
- FastMCP is the de facto standard for Python MCP servers (powers ~70% of all MCP servers)
- `@mcp.tool` decorator pattern eliminates all JSON-RPC boilerplate
- Auto-generates tool schemas from Python type hints + docstrings
- `mcp.run()` with default stdio transport = one line to start

**Alternative considered:** `mcp[cli]` (official SDK with bundled FastMCP v1)
**Rejected because:** Standalone `fastmcp` is more actively maintained with v2/v3 features

---

### ADR-2: `bring-api` PyPI package as API layer

**Decision:** Use `pip install bring-api` (miaucl/bring-api)

**Rationale:**
- Actively maintained (44 releases, last Oct 2025)
- Handles auth, token refresh, error handling
- Used in Home Assistant (battle-tested)
- Async-first with aiohttp (FastMCP supports async tools natively)
- Saves implementing the entire unofficial API from scratch

**Alternative considered:** Raw HTTP calls to Bring! API
**Rejected because:** Unnecessary complexity; would need to maintain auth logic ourselves

---

### ADR-3: stdio transport

**Decision:** stdio (default)

**Rationale:**
- Required by Claude Desktop
- No port configuration, firewall rules, or network setup
- Standard for local MCP servers

**Alternative considered:** SSE/HTTP transport
**Deferred to v2:** If Alex wants to expose this as a shared service

---

### ADR-4: Environment variable credentials

**Decision:** `BRING_EMAIL` + `BRING_PASSWORD` env vars

**Rationale:**
- Claude Desktop `claude_desktop_config.json` supports `env` block natively
- No credentials in code or config files checked into git
- Simple to set up, easy to understand

**Alternative considered:** Config file (`~/.mcp-bring/config.toml`)
**Rejected because:** More complexity for no benefit in single-user local use case

---

### ADR-5: Single persistent session

**Decision:** Create one `aiohttp.ClientSession` + `Bring` instance at startup, share across all tool calls

**Rationale:**
- `bring-api` docs warn against multiple sessions per thread
- Auto-refresh logic in `bring-api` is stateful (stores refresh token on the instance)
- Connection pooling benefits from reuse

**Implementation:** Use `asynccontextmanager` lifespan in FastMCP to init/teardown the session

---

## Project Structure

```
mcp-bring/
├── PRD.md                    # Product requirements
├── ARCHITECTURE.md           # This file
├── TASKS.md                  # Task breakdown
├── README.md                 # Setup & usage guide
├── pyproject.toml            # Package config (uv/pip compatible)
├── .env.example              # Template for credentials
├── src/
│   └── mcp_bring/
│       ├── __init__.py
│       └── server.py         # Main FastMCP server (all tools defined here)
└── tests/
    ├── __init__.py
    └── test_server.py        # Unit tests (mock bring-api)
```

---

## Tool Call Flow

```
Claude: "Add milk to my shopping list"
    │
    ▼ (MCP tool call)
get_lists()  →  [{"listUuid": "abc123", "name": "Grocery", ...}]
    │
    ▼ (MCP tool call)
add_item(list_uuid="abc123", item_name="Milk", spec=None)
    │
    ▼ (bring-api)
bring.save_item("abc123", "Milk", "")
    │
    ▼ (HTTPS)
POST api.getbring.com/rest/v2/lists/abc123/items
    │
    ◀ 200 OK
    │
    ▼
"Done! Added Milk to your Grocery list."
```

---

## Error Handling

| Scenario | Handling |
|---|---|
| Missing credentials at startup | Raise at init, log clear message |
| Auth failure (invalid creds) | `BringAuthException` → `ToolError` with helpful message |
| Token expiry | Auto-handled by `bring-api._request()` |
| Network error | `BringRequestException` → `ToolError` |
| Item not found | Bring! API returns 200 with empty, handle gracefully |
| List not found | Raise `ToolError` with list of valid lists |
