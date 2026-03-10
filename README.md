# mcp-bring

An MCP (Model Context Protocol) server for the [Bring! shopping list app](https://getbring.com). 
Lets Claude and other AI assistants read and manage your Bring! shopping lists.

> ⚠️ **Unofficial API**: This uses the reverse-engineered Bring! API. Not affiliated with Bring! Labs AG.

---

## What it does

Talk to your shopping list naturally:

- _"What's on my shopping list?"_
- _"Add milk, eggs, and oat milk to the grocery list"_
- _"Mark butter as purchased"_
- _"Add all ingredients for pasta carbonara to my list"_

---

## Available Tools

| Tool | Description |
|---|---|
| `get_lists` | Get all your Bring! shopping lists |
| `get_list_items` | Get items in a list (to-buy + recently purchased) |
| `get_list_details` | Get detailed item info (attributes, images) |
| `get_list_users` | Get users sharing a list |
| `get_list_activity` | Get recent activity on a list |
| `add_item` | Add a single item (with optional spec/notes) |
| `add_items` | Add multiple items at once (batch) |
| `complete_item` | Mark item as purchased |
| `remove_item` | Remove item from list entirely |
| `update_item_spec` | Update spec/notes on an item |
| `get_account_info` | Get your Bring! account info |

---

## Setup

### 1. Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A Bring! account

### 2. Install

```bash
# Clone or copy this project
cd mcp-bring

# Install with uv
uv pip install -e .

# Or with pip
pip install -e .
```

### 3. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bring": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/mcp-bring", "mcp-bring"],
      "env": {
        "BRING_EMAIL": "your@email.com",
        "BRING_PASSWORD": "your_password"
      }
    }
  }
}
```

Replace `/path/to/mcp-bring` with the actual path to this directory.

### 4. Restart Claude Desktop

Quit and reopen Claude Desktop. You should see "Bring! Shopping Lists" in the tools available.

---

## Development

```bash
# Install dev deps
uv pip install -e ".[dev]"

# Test the server interactively
fastmcp dev src/mcp_bring/server.py

# Run tests
pytest

# Lint
ruff check src/
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BRING_EMAIL` | Yes | Your Bring! account email |
| `BRING_PASSWORD` | Yes | Your Bring! account password |
| `BRING_LIST_ALLOWLIST` | No | Comma-separated list names or UUIDs to restrict access (see below) |

### List Allowlist (`BRING_LIST_ALLOWLIST`)

By default the server exposes **all** your Bring! lists. Set `BRING_LIST_ALLOWLIST` to limit which lists Claude can see and interact with.

```bash
# Restrict to a single list by name
BRING_LIST_ALLOWLIST=Groceries

# Multiple lists (names, UUIDs, or a mix)
BRING_LIST_ALLOWLIST=Groceries,Hardware Store
BRING_LIST_ALLOWLIST=Groceries,a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

When the allowlist is active:
- `get_lists` returns only the allowed lists
- Any tool that targets a list UUID not on the allowlist returns a clear error

The allowlist is resolved **once at startup** — list names are looked up and converted to UUIDs, so renaming a list in the Bring! app requires a server restart to pick up the change.

To use it with Claude Desktop, add it to the `env` block:

```json
{
  "mcpServers": {
    "bring": {
      "command": "uv",
      "args": ["run", "--project", "/path/to/mcp-bring", "mcp-bring"],
      "env": {
        "BRING_EMAIL": "your@email.com",
        "BRING_PASSWORD": "your_password",
        "BRING_LIST_ALLOWLIST": "Groceries"
      }
    }
  }
}
```

---

## Troubleshooting

**"Authentication failed"** — Check your email/password. Note: if you use social login (Google/Apple), you may need to set a Bring! password separately.

**"Missing credentials"** — Make sure `BRING_EMAIL` and `BRING_PASSWORD` are set in the Claude Desktop config `env` block.

**Server not appearing in Claude Desktop** — Check the config JSON is valid, restart Claude Desktop, check logs at `~/Library/Logs/Claude/`.

---

## License

MIT
