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

Set up the Python environment and run the fetch script, which calls `list_regulations` and `list_documents` via the MCP SDK, produces the summary, and compares regulation filenames against repository document filenames.

```bash
# Prepare virtual environment
cd orca
uv sync

# Run with defaults (workspace 1, repository 6)
uv run regulation-list-fetch --config assets/mcp_config.json

# Specify a different workspace
uv run regulation-list-fetch --config assets/mcp_config.json --workspace-id 2

# Specify a different repository
uv run regulation-list-fetch --config assets/mcp_config.json --repository-id 5

# Save summary to a custom path
uv run regulation-list-fetch --config assets/mcp_config.json --output assets/regulations_summary.json
```

**Arguments:**
- `--config` (required): Path to MCP config JSON
- `--workspace-id` (optional): Workspace ID to query (default: `1`)
- `--repository-id` (optional): Repository ID to fetch documents for filename comparison (default: `6`)
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
3. Calls `list_documents` with the provided `workspaceId` and `repositoryId`
4. Saves the raw regulations to `assets/regulations.json`
5. Saves the raw documents to `assets/documents.json` (reusable by other scripts)
6. Computes and saves a summary (including filename comparison) to the specified output path
7. Prints the summary and filename comparison to the console

### Step 2: Review the Summary

The summary JSON contains the following fields:

| Field | Description |
|---|---|
| `total` | Total number of regulations |
| `by_category` | Count per `category` value |
| `by_jurisdiction` | Count per `jurisdiction` value |
| `by_included` | Count per `included` boolean (`true` / `false`) |
| `filename_comparison` | Diff between regulation filenames and document filenames |

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
  },
  "filename_comparison": {
    "total_regulation_filenames": 40,
    "total_document_filenames": 38,
    "matched": 37,
    "only_in_regulations": ["reg_a.pdf", "reg_b.pdf", "reg_c.pdf"],
    "only_in_documents": ["doc_x.pdf"]
  }
}
```

Console output mirrors the same breakdown in a human-readable format.

### Step 3: Filename Comparison

After fetching both regulations and documents, the script automatically compares filenames:

1. **Build regulation filename set**: Aggregates all unique filenames from the `filenames` field across all regulations.
2. **Build document filename set**: Collects all unique `filename` values from the repository documents.
3. **Compute the diff**: Identifies filenames present in one set but not the other.

The comparison is included in the summary JSON under `filename_comparison` and printed to the console:

```
=== Filename Comparison ===
Regulation filenames: 1469
Document filenames:   1471
Matched:              1469
Only in regulations:  0
Only in documents:    2

  Filenames in documents but not in regulations:
    - California Civil Rights Council Employment Regulations Regarding Automated-Decision Systems (FEHA ADS Regulations).pdf
    - Columbus - 0709 - 2023.pdf
```

The `assets/documents.json` file is written by the script and can be reused by other skills (e.g., rag-document-linking, rag-metadata-report) without re-fetching.

## Key Points

1. **Default workspace:** If `--workspace-id` is omitted, the script defaults to workspace `1`.
2. **Default repository:** If `--repository-id` is omitted, the script defaults to repository `6` (COMPLIANCE).
3. **Full fetch:** The script uses `limit: 2147483647` to retrieve the complete dataset unless the user explicitly requests otherwise.
4. **Raw data preserved:** The full `regulations` array is always saved to `assets/regulations.json`. Documents are saved to `assets/documents.json` for reuse.
5. **Filename comparison:** The script automatically compares regulation filenames against document filenames and includes the diff in the summary.
6. **No HTML report:** Unlike jurisdictions or law-changes skills, this skill outputs a lightweight JSON summary suitable for quick inspection or downstream processing.
