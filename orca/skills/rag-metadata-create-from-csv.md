# Create RAG Metadata from CSV

## Overview

Creates or updates RAG metadata key-value pairs for selected documents, driven entirely by a CSV file. Unlike `create_rag_jurisdiction_metadata` (which is hardcoded to `jurisdiction_code`), this skill handles **any metadata key** validated against the live schema from `list_rag_data_schemas`.

- Tools used: `list_rag_data_schemas`, `list_rag_metadata`, `create_rag_metadata`, `update_rag_metadata`
- Workspace 1, Compliance Repository ID 6

## Prerequisites

- Orca MCP server access
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- `assets/compliance_documents.json` — run `fetch-compliance-documents` first if stale
- MCP config JSON (see `rag-metadata-create-jurisdiction.md` Step 1)

## CSV Format

One metadata operation per row. A document can appear multiple times (for different keys).

| Column | Description |
| :--- | :--- |
| `filename` | Document filename — must match exactly a filename in `compliance_documents.json` |
| `key` | Metadata key name — must be a valid key from `list_rag_data_schemas` |
| `value` | String value to write |

**Example:**

```csv
filename,key,value
Nevada Administrative Code Chapter 686B Insurance.pdf,jurisdiction_code,US-NV
Wisconsin Statutes Chapter 600.pdf,jurisdiction_code,US-WI
Wisconsin Statutes Chapter 600.pdf,category,insurance
```

## Usage

```bash
cd orca
uv sync

# Run with schema validation (default)
uv run rag-metadata-create-from-csv --config assets/mcp_config.json --csv input.csv

# Skip key validation against list_rag_data_schemas
uv run rag-metadata-create-from-csv --config assets/mcp_config.json --csv input.csv --skip-schema-validation
```

**Parameters:**
- `--config` (required): Path to MCP config JSON.
- `--csv` (required): Path to input CSV file.
- `--skip-schema-validation` (optional): Bypass key validation (use if `list_rag_data_schemas` is unavailable).

## Validation

Before any writes, the script validates:

1. **Filename check**: Every `filename` in the CSV must exist in `compliance_documents.json`. Unmatched filenames are printed and the script aborts.
2. **Schema key check**: Calls `list_rag_data_schemas` at startup to fetch valid key names. Any `key` not in that set is printed and the script aborts. Use `--skip-schema-validation` to bypass.

## Upsert Logic

For each CSV row, the script:

1. Calls `list_rag_metadata` to read the document's current metadata.
2. Compares the current value for `key`:
   - **Key absent** → `create_rag_metadata`
   - **Value matches** → skip (idempotent)
   - **Value differs** → `update_rag_metadata`

Re-running the same CSV is safe — rows where the value already matches are skipped.

## INTERNAL Error Handling

`create_rag_metadata` often returns `INTERNAL` errors even on success. The script:

1. Detects INTERNAL errors
2. Re-verifies via `list_rag_metadata`
3. Treats as success if the value now matches — logs as false-negative

## Output

```
Fetching available RAG data schemas...
Valid schema keys: ['category', 'jurisdiction_code']
Processing 3 rows...
Processed 3/3 rows...

--- Summary ---
  Created: 2
  Updated: 0
  Skipped: 1 (value already matched)
  Failed:  0
Done.
```

## Verification

After running, spot-check a few documents using `list_rag_metadata` to confirm the metadata was written correctly.
