# Upsert RAG Metadata

## Overview

Reliably set or update a single metadata entry for a given RAG file using the Orca MCP tools. This skill implements a "check-then-act" pattern with verification to ensure data consistency and handle potential API inconsistencies (such as false-negative errors).

## Prerequisites

- Access to the Orca MCP server
- The full resource name of the RAG file (e.g., `projects/.../ragFiles/...`)
- The metadata `key` and the desired `value` (string, integer, float, or boolean)
- **Firestore Access**: Google Cloud credentials configured for the `regulations` database in project `visdomapp-1` to update the `rag_metadata_cache` collection.

## Workflow

### Step 1: Check Existing State (`list_rag_metadata`)

First, determine if the metadata entry already exists for the given RAG file.

Call `mcp__orca__list_rag_metadata` with the `ragFileName`.

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

### Step 2: Act (`create_rag_metadata` or `update_rag_metadata`)

Choose the appropriate tool based on Step 1:

#### Case A: Entry does not exist → Use `create_rag_metadata`
Call `mcp__orca__create_rag_metadata` with:
- `ragFileName`: The RAG file resource name.
- `entries`: An array containing one object with `key` and the appropriate value field (e.g., `valueStr`, `valueInt`).

**Example:**
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
Call `mcp__orca__update_rag_metadata` with:
- `name`: The full resource name of the metadata entry (from Step 1).
- `key`: The metadata key.
- The appropriate value field (e.g., `valueStr`).

**Example:**
```json
{
  "name": "projects/.../ragFiles/.../ragMetadata/jurisdiction_code",
  "key": "jurisdiction_code",
  "valueStr": "US-NY"
}
```

### Step 3: Verify (`list_rag_metadata` again)

Always verify that the change was applied successfully, especially because some Orca MCP tools may return "INTERNAL" errors even when the operation succeeds (false negatives).

Call `mcp__orca__list_rag_metadata` again with the same `ragFileName`.

**Verification Logic:**
1. Check if the metadata entry now exists.
2. Confirm that the `value` matches the expected value you intended to set.
3. If the value matches, the upsert is complete.
4. If the value does not match or the entry is missing, report the failure and suggest retrying.

### Step 4: Sync Firestore Cache

After successfully verifying the metadata change in Vertex AI, synchronize the `rag_metadata_cache` collection in Firestore to ensure consistency with future reports.

1. **Identify the Document**: The cache document ID is the `filename` associated with the RAG file.
2. **Fetch Current Cache State**: Call `get_rag_metadata` from `scripts/rag_metadata_report/firestore_utils.py` using the filename.
3. **Update Metadata**: 
   - If the metadata entry exists in the cached list, update its value.
   - If it doesn't exist, append a new entry `{"key": "your_key", "value": "your_value"}` to the `metadata` array.
4. **Save to Firestore**: Call `save_rag_metadata` with the updated metadata list.

**Python Example for Cache Sync:**
```python
from scripts.rag_metadata_report.firestore_utils import get_firestore_client, get_rag_metadata, save_rag_metadata
import asyncio

async def sync_cache(filename, rag_file_name, key, new_value):
    client = get_firestore_client()
    try:
        # Get existing cache
        cached = await get_rag_metadata(client, filename)
        metadata = cached["metadata"] if cached else []
        
        # Update or add the key
        updated = False
        for entry in metadata:
            if entry.get("key") == key:
                entry["value"] = new_value
                updated = True
                break
        
        if not updated:
            metadata.append({"key": key, "value": new_value})
            
        # Save back to Firestore
        await save_rag_metadata(
            client=client,
            rag_file_name=rag_file_name,
            filename=filename,
            metadata=metadata
        )
    finally:
        client.close()

# Usage
# asyncio.run(sync_cache("my_doc.pdf", "projects/...", "jurisdiction_code", "US-CA"))
```

## Important Notes

1. **Value Types:** Ensure you use the correct value field for the data type:
   - Strings: `valueStr`
   - Integers: `valueInt`
   - Floats: `valueFloat`
   - Booleans: `valueBool`
2. **False Negatives:** If `create` or `update` returns an error containing "INTERNAL", do not assume failure. Always proceed to Step 3 (Verification) to check the actual state in Firestore/The database.
3. **Resource Names:** `update_rag_metadata` requires the specific metadata resource `name`, not just the `ragFileName`. Always get this from the `list` call.
