# Upsert RAG Metadata

## Overview

Reliably set or update a single metadata entry for a given RAG file using the Orca MCP tools. This skill implements a "check-then-act" pattern with verification to ensure data consistency and handle potential API inconsistencies (such as false-negative errors).

All MCP communication is handled via `scripts/common/tools/mcp_wrapper_base.py`.

- Tools used: `list_rag_metadata`, `create_rag_metadata`, `update_rag_metadata`

## Prerequisites

- Access to the Orca MCP server
- The full resource name of the RAG file (e.g., `projects/.../ragFiles/...`)
- The metadata `key` and the desired `value` (string, integer, float, or boolean)
- **Firestore Access**: Google Cloud credentials configured for the `regulations` database in project `visdomapp-1` to update the `rag_metadata_cache` collection.

## Pipeline

### Step 1: Run the Upsert Script

The script at `scripts/rag_metadata_upsert/upsert_rag_metadata.py` automates the full check-act-verify-sync workflow in a single command.

```bash
# Prepare virtual environment
cd orca
uv sync

# Basic upsert (with Firestore cache sync)
uv run rag-metadata-upsert \
  --config assets/mcp_config.json \
  --rag-file projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5702363560879151916 \
  --key jurisdiction_code \
  --value US

# Upsert with explicit filename for cache sync
uv run rag-metadata-upsert \
  --config assets/mcp_config.json \
  --rag-file projects/.../ragFiles/... \
  --key jurisdiction_code \
  --value US-CA \
  --filename "29 CFR Part 100-700.pdf"

# Skip Firestore cache sync
uv run rag-metadata-upsert \
  --config assets/mcp_config.json \
  --rag-file projects/.../ragFiles/... \
  --key jurisdiction_code \
  --value US \
  --no-cache-sync
```

**Arguments:**
- `--config` (required): Path to MCP config JSON
- `--rag-file` (required): Full RAG file resource name
- `--key` (required): Metadata key (e.g., `jurisdiction_code`)
- `--value` (required): Metadata value — the script auto-detects the type:
  - `true`/`false` → boolean (`valueBool`)
  - Numeric integers → integer (`valueInt`)
  - Numeric floats → float (`valueFloat`)
  - Everything else → string (`valueStr`)
- `--filename` (optional): Document filename for Firestore cache key. If omitted, the script looks it up from `assets/rag_files.json` by matching the RAG file name.
- `--no-cache-sync` (optional): Skip Firestore cache synchronization after upsert.

**What happens:**
1. **Check**: Calls `list_rag_metadata` to see if the key already exists.
   - If the value already matches, exits early ("Nothing to do").
2. **Act**: Calls `create_rag_metadata` (key doesn't exist) or `update_rag_metadata` (key exists, value differs).
3. **Verify**: Calls `list_rag_metadata` again to confirm the change. Fails with exit code 1 if verification fails.
4. **Sync Firestore cache**: Updates the `rag_metadata_cache` collection to keep it consistent with Vertex AI.

### Step 2: Review Output

Example output:

```
Config loaded (URL: https://orcaservices-360095844563.us-central1.run.app)
Target: projects/.../ragFiles/5702363560879151916
Key:    jurisdiction_code
Value:  US (valueStr)

Step 1: Checking existing metadata...
  Found existing: jurisdiction_code=US-PR

Step 2: Updating metadata entry (US-PR -> US)...

Step 3: Verifying...
  VERIFIED: jurisdiction_code=US

Step 4: Syncing Firestore cache...
  Cache: jurisdiction_code US-PR -> US
  Firestore cache synced for '29 CFR Part 100-700.pdf'

Done.
```

---

## Manual Workflow (Reference)

If you need to call the MCP tools individually instead of using the script:

### Manual Step 1: Check Existing State (`list_rag_metadata`)

Call `list_rag_metadata` with the `ragFileName`.

**Example:**
```json
{
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5685605197563873605"
}
```

**Analysis:**
- Parse the `metadata` array from the response.
- Look for an entry where `key` matches your target key.
- If found, note the current `value` and the full `name` (resource path) of the metadata entry.
- If not found, you will need to use `create_rag_metadata`.

### Manual Step 2: Act (`create_rag_metadata` or `update_rag_metadata`)

#### Case A: Entry does not exist → Use `create_rag_metadata`
```json
{
  "ragFileName": "projects/.../ragFiles/...",
  "entries": [
    {
      "key": "jurisdiction_code",
      "valueStr": "US-CA"
    }
  ]
}
```

#### Case B: Entry exists → Use `update_rag_metadata`
```json
{
  "name": "projects/.../ragFiles/.../ragMetadata/jurisdiction_code",
  "key": "jurisdiction_code",
  "valueStr": "US-NY"
}
```

### Manual Step 3: Verify (`list_rag_metadata` again)

Always verify that the change was applied successfully, especially because some Orca MCP tools may return "INTERNAL" errors even when the operation succeeds (false negatives).

### Manual Step 4: Sync Firestore Cache

Use the `sync_cache` pattern from `scripts/common/firestore_utils.py`:
- Fetch existing cache via `get_rag_metadata`
- Update or append the metadata entry
- Save via `save_rag_metadata`

## Important Notes

1. **Value Types:** The script auto-detects value types. When calling tools manually, use the correct value field:
   - Strings: `valueStr`
   - Integers: `valueInt`
   - Floats: `valueFloat`
   - Booleans: `valueBool`
2. **False Negatives:** If `create` or `update` returns an error containing "INTERNAL", do not assume failure. Always proceed to Step 3 (Verification) to check the actual state.
3. **Resource Names:** `update_rag_metadata` requires the specific metadata resource `name`, not just the `ragFileName`. Always get this from the `list` call.
4. **Filename lookup:** The script attempts to resolve the document filename from `assets/rag_files.json` for Firestore cache sync. If this file is stale or missing, use `--filename` explicitly.
