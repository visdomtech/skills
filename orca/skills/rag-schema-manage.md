# Manage RAG Data Schemas

## Overview

Interactively list, add, or delete RAG data schema keys for a Vertex AI RAG corpus. All MCP calls are made via the `rag-schema-manage` Python script using the MCP client SDK — the agent does **not** call MCP tools directly.

- Script: `orca/scripts/rag_schema_manage/manage_rag_data_schemas.py`
- Entry point: `rag-schema-manage`
- MCP tools used (by the script): `list_rag_data_schemas`, `create_rag_data_schema`, `delete_rag_data_schema`

## Prerequisites

- Orca MCP server access
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- MCP config JSON (see `rag-metadata-create-jurisdiction.md` Step 1 for setup)
- `corpusName` — the full resource name of the RAG corpus (e.g. `projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088`). See `AGENTS.md` "Well-Known Data" for corpus names.

## Workflow

### Step 1: List Current Schemas

```bash
cd orca
uv run rag-schema-manage --config assets/mcp_config.json \
    --corpus-name projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088 \
    --action list
```

The script prints a numbered table of all current schema keys and their data types for the given corpus. Display this to the user.

Then ask the user: **"Would you like to (A) add a new schema key, (B) delete an existing schema key, or (C) exit?"**

---

### Option A: Add New Schema Key

Ask the user:
1. **Key name** — "What key name would you like to add? (no spaces, e.g. `doc_type`)"
2. **DataType** — "Select a data type: `INTEGER`, `FLOAT`, `STRING`, `DATETIME`, `BOOLEAN`. Press Enter to default to `STRING`."

Then run:

```bash
uv run rag-schema-manage --config assets/mcp_config.json \
    --corpus-name projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088 \
    --action add \
    --key <user-provided-key> \
    --data-type <selected-type>
```

The script automatically:
- Checks the key doesn't already exist (aborts if it does)
- Calls `create_rag_data_schema`
- Reprints the updated schema table to confirm the addition

---

### Option B: Delete Existing Schema Key

**Agent-level protection:** If the user selects or names `jurisdiction_code`, refuse immediately — do not run the script at all:

> "`jurisdiction_code` is a protected key and cannot be deleted."

For all other keys, use a two-step confirmation:

**Step 1 — Show what will be deleted** (no `--confirm` flag):

```bash
uv run rag-schema-manage --config assets/mcp_config.json \
    --corpus-name projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088 \
    --action delete \
    --key <selected-key>
```

The script prints the current schema list and then: "Pass --confirm to proceed with deletion of `<key>`."

Ask the user: **"Are you sure you want to permanently delete `<key>`? This cannot be undone. Reply DELETE (all caps) to confirm."**

**Step 2 — Execute deletion** (only if user replied exactly "DELETE"):

```bash
uv run rag-schema-manage --config assets/mcp_config.json \
    --corpus-name projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088 \
    --action delete \
    --key <selected-key> \
    --confirm
```

The script calls `delete_rag_data_schema` and reprints the updated schema table confirming the key is gone.

If the user's reply is anything other than "DELETE", abort — do not run the second command.

---

## Important Notes

- `jurisdiction_code` is a protected key — the agent must refuse to delete it before running any script command.
- `DataType` defaults to `STRING` if the user does not specify.
- `CorpusName` must be provided via `--corpus-name`. Use the value from `AGENTS.md` "Well-Known Data".
- The `Granularity` parameter is intentionally omitted from all `create_rag_data_schema` calls.
