# Regulation List and Summary

## Overview

Fetch all regulations for a given workspace and produce a structured summary broken down by status, category, jurisdiction, and inclusion status.

All MCP communication is handled via `scripts/common/tools/mcp_wrapper_base.py`.

## Prerequisites

- Access to the Orca MCP server
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- MCP config JSON (see Step 1)

## Pipeline

### Step 1: Prepare Environment and Run Script

Set up the Python environment and run the fetch script, which calls `list_regulations` via the MCP SDK and produces the summary automatically.

```bash
# Prepare virtual environment
cd orca
uv sync

# Run with defaults (workspace 1)
uv run regulation-list-fetch --config assets/mcp_config.json

# Specify a different workspace
uv run regulation-list-fetch --config assets/mcp_config.json --workspace-id 2

# Save summary to a custom path
uv run regulation-list-fetch --config assets/mcp_config.json --output assets/regulations_summary.json
```

**Arguments:**
- `--config` (required): Path to MCP config JSON
- `--workspace-id` (optional): Workspace ID to query (default: `1`)
- `--output` (optional): Output JSON path for the summary. Default: `assets/regulations_summary.json`

**MCP config format** (`assets/mcp_config.json`):
```json
{
  "type": "http",
  "url": "https://orcaservices-360095844563.us-central1.run.app",
  "headers": {
    "X-API-KEY": "your-api-key-here"
  }
}
```

The script:
1. Connects to the Orca MCP server via the MCP SDK
2. Calls `list_regulations` with the provided `workspaceId` and `limit: 2147483647`
3. Saves the raw data to `assets/regulations.json`
4. Computes and saves a summary to the specified output path
5. Prints the summary to the console

### Step 2: Review the Summary

The summary JSON contains the following fields:

| Field | Description |
|---|---|
| `total` | Total number of regulations |
| `by_category` | Count per `category` value |
| `by_jurisdiction` | Count per `jurisdiction` value |
| `by_included` | Count per `included` boolean (`true` / `false`) |

Example output:
```json
{
  "total": 42,
  "by_category": {
    "EMPLOYMENT": 20,
    "PRIVACY": 15,
    "LABOR": 7
  },
  "by_jurisdiction": {
    "US-CA": 10,
    "US-NY": 8,
    "US-FEDERAL": 5
  },
  "by_included": {
    "true": 35,
    "false": 7
  }
}
```

Console output mirrors the same breakdown in a human-readable format.

## Key Points

1. **Default workspace:** If `--workspace-id` is omitted, the script defaults to workspace `1`.
2. **Full fetch:** The script uses `limit: 2147483647` to retrieve the complete dataset unless the user explicitly requests otherwise.
3. **Raw data preserved:** The full `regulations` array is always saved to `assets/regulations.json` for reuse or further analysis.
4. **No HTML report:** Unlike jurisdictions or law-changes skills, this skill outputs a lightweight JSON summary suitable for quick inspection or downstream processing.
