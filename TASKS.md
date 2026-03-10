# Task Breakdown: mcp-bring

**Status:** Planning  
**Updated:** 2026-03-10

---

## Phase 1: Foundation (Est. ~2h)

### T-001 — Project setup
- [ ] Init project with `uv init` (or create `pyproject.toml` manually)
- [ ] Add dependencies: `fastmcp`, `bring-api`, `aiohttp`
- [ ] Add dev deps: `pytest`, `pytest-asyncio`, `python-dotenv`
- [ ] Create `src/mcp_bring/__init__.py`
- [ ] Create `.env.example`
- [ ] Create `README.md` skeleton

**Acceptance:** `uv run mcp-bring --help` works (even if server does nothing yet)

---

### T-002 — Auth & session management
- [x] Read `BRING_EMAIL` / `BRING_PASSWORD` from env at startup
- [x] Create `aiohttp.ClientSession` + `Bring(session, email, password)` in FastMCP lifespan
- [x] Call `await bring.login()` on startup
- [x] Pass bring instance to all tools via FastMCP context/lifespan
- [x] Handle missing env vars with clear error message

**Acceptance:** Server starts, logs "Logged in as <email>", exits cleanly on Ctrl+C

---

### T-002b — List allowlist (BRING_LIST_ALLOWLIST)
- [x] Read `BRING_LIST_ALLOWLIST` from env at startup (optional, comma-separated names/UUIDs)
- [x] Resolve list names → UUIDs by calling `load_lists()` once during lifespan
- [x] Store resolved set of allowed UUIDs in lifespan context
- [x] `get_lists` filters returned lists to allowed UUIDs when allowlist is active
- [x] All per-list tools (`get_list_items`, `get_list_details`, `get_list_users`, `get_list_activity`, `add_item`, `add_items`, `complete_item`, `remove_item`, `update_item_spec`) raise `ToolError` for non-allowed list UUIDs
- [x] When `BRING_LIST_ALLOWLIST` is unset/empty, all lists are accessible (no breaking change)

**Acceptance:** With allowlist set to one list name, `get_lists` returns only that list; calling any tool with a non-allowed UUID returns a clear ToolError.

---

## Phase 2: Core Tools (Est. ~3h)

### T-003 — Read tools
- [ ] `get_lists` — returns list name, uuid, theme, members count
- [ ] `get_list_items` — returns purchase (to-buy) + recently (purchased) items for a list
- [ ] `get_account_info` — returns email, name, uuid of logged-in user

**Acceptance:** Can run via `fastmcp dev server.py` and call tools manually

---

### T-004 — Write tools
- [ ] `add_item(list_uuid, item_name, spec?)` — add single item
- [ ] `add_items(list_uuid, items)` — batch add (uses `batch_update_list`)
- [ ] `complete_item(list_uuid, item_name)` — mark as purchased
- [ ] `remove_item(list_uuid, item_name)` — remove from list
- [ ] `update_item_spec(list_uuid, item_name, spec)` — update notes/details

**Acceptance:** Round-trip test: add → verify → complete → verify → remove → verify

---

### T-005 — Advanced tools (optional for v1)
- [ ] `get_list_users(list_uuid)` — who's sharing this list
- [ ] `get_list_activity(list_uuid)` — recent activity feed
- [ ] `get_list_details(list_uuid)` — detailed item info (images, attributes)

---

## Phase 3: Polish (Est. ~1h)

### T-006 — Error handling
- [ ] Wrap all tool calls in try/except
- [ ] Map `BringAuthException` → helpful `ToolError`
- [ ] Map `BringRequestException` → `ToolError`
- [ ] Validate `list_uuid` exists before write operations
- [ ] Friendly error when env vars missing

---

### T-007 — Tests
- [ ] Mock `bring-api` with pytest fixtures
- [ ] Test `get_lists` returns expected format
- [ ] Test `add_item` calls correct API method
- [ ] Test `complete_item` behavior
- [ ] Test auth error handling

---

### T-008 — README & Claude Desktop config
- [ ] Installation instructions (uv + pip variants)
- [ ] Claude Desktop config snippet
- [ ] Tool reference table
- [ ] Troubleshooting section

---

## Phase 4: Packaging (optional, post-v1)

### T-009 — PyPI packaging
- [ ] Polish `pyproject.toml` (description, classifiers, entry point)
- [ ] Test `pip install .` and `uvx mcp-bring`
- [ ] Publish to PyPI as `mcp-bring`

---

## Prioritization

**Must have (v0.1):** T-001, T-002, T-003, T-004, T-006, T-008  
**Should have:** T-007 (tests), T-005 (advanced tools)  
**Nice to have:** T-009 (PyPI)

---

## Notes / Open Questions

- [ ] Test with a real Bring! account to verify API responses match `bring-api` types
- [ ] Check if `batch_update_list` is better than `save_item` for single items too
- [ ] Decide: should `get_list_items` accept list name OR uuid? (name is more LLM-friendly; resolve to uuid internally)
- [ ] Consider: tool to list available lists should run first so LLM knows valid list_uuids
