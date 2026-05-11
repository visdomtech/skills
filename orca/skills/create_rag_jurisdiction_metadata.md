# Create RAG Jurisdiction Metadata

## Overview

This skill describes how to create `jurisdiction_code` metadata for RAG files by matching included regulations to their corresponding documents in the Compliance Repository. This ensures that RAG search results can be filtered or boosted by jurisdiction.

## Prerequisites

- Access to the Orca MCP server
- MCP Python SDK installed: `pip install mcp`
- MCP server configuration JSON file (see Step 1)
- The following tools used by the script: `list_regulations`, `list_documents`, `create_rag_metadata`, `update_rag_metadata`, `list_rag_metadata`
- Well-known data: Workspace 1, Compliance Repository ID 6

## Step 1: Prepare MCP Configuration

Create a JSON file with your MCP server configuration:

```json
{
  "type": "http",
  "url": "https://orcaservices-360095844563.us-central1.run.app",
  "headers": {
    "X-API-KEY": "your-api-key-here"
  }
}
```

Save this file (e.g., `orca/assets/mcp_config.json`). **Never commit API keys to version control.**

## Step 2: Run the Script

The script `orca/scripts/create_rag_jurisdiction_metadata.py` performs the entire workflow automatically:

1. Fetches included regulations via `list_regulations`
2. Fetches compliance documents via `list_documents`
3. Matches regulations to documents by filename
4. Creates intermediate batch files in `orca/cache/` for debugging
5. Processes each match by checking existing metadata and creating/updating as needed
6. Handles false negative INTERNAL errors by verifying after each operation
7. Tracks progress for checkpoint-based resumption

### Script Usage

```bash
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config <path_to_mcp_config.json>
```

**Parameters:**
- `--config` (required): Path to the MCP server configuration JSON file.

### What the Script Does

The script performs the following steps automatically:

1. **Fetch Data**: Calls `list_regulations` and `list_documents` to get current state
2. **Match Regulations**: Filters for `included: true` regulations and matches them to documents by filename
3. **Generate Batches**: Saves intermediate batch files to `orca/assets/` (for debugging/audit trail)
4. **Process Metadata**: For each match:
   - Checks if `jurisdiction_code` metadata already exists via `list_rag_metadata`
   - If missing: calls `create_rag_metadata`
   - If exists with different value: calls `update_rag_metadata`
   - If exists with same value: skips
   - Verifies result immediately after create/update
5. **Handle Errors**: Detects false negative INTERNAL errors and verifies success anyway
6. **Track Progress**: Updates progress file after each batch to enable resume

## Step 3: Checkpoint-Based Resumption

The script automatically tracks progress in `orca/assets/rag_meta_batch_progress.json`:

```json
{
  "current_batch": "rag_meta_batch_4.json",
  "current_batch_index": 0,
  "completed_entries": 700,
  "total_entries": 1347,
  "last_updated": "2026-05-11T21:30:00Z"
}
```

**Resume Behavior:**
- If interrupted, simply re-run the same command
- The script reads `current_batch` and `current_batch_index` to determine where to resume
- It skips all batch files before `current_batch`, then starts processing that batch from `current_batch_index`
- Progress is updated every 10 entries to minimize data loss on interruption
- When a batch completes, `current_batch_index` resets to 0 and advances to the next batch file

## Error Handling

### False Negative INTERNAL Errors

The `create_rag_metadata` tool frequently returns `INTERNAL` errors even when the operation succeeds. The script handles this by:

1. Detecting INTERNAL errors in the response
2. Immediately calling `list_rag_metadata` to verify
3. If metadata appears in the verification, treating it as success
4. Logging as "Created & Verified (false negative handled)"

### Metadata Decision Logic

Before writing metadata, the script always checks existing state:

- **Key missing** → Call `create_rag_metadata`
- **Key exists, value matches** → Skip (no action needed)
- **Key exists, value differs** → Call `update_rag_metadata`

This prevents timeout errors from attempting to create metadata on an existing key.

### Verification Pattern

After every create/update operation, the script immediately verifies by calling `list_rag_metadata` and comparing the result to the expected value. This ensures data integrity.

## Verification

After the script completes, verify results:

### Sample Check

Pick a few RAG file names and call `list_rag_metadata` to confirm the `jurisdiction_code` is present:

```bash
# Use MCP tool directly or another script
# Call list_rag_metadata for specific ragFileNames
```

### Count Validation

Compare the number of successfully processed entries reported by the script with the total number of matched regulations. They should be equal (minus any legitimate failures).

### Intermediate Batch Files

The script saves intermediate batch files to `orca/cache/` for debugging and audit purposes. These can be inspected to verify the matching logic was correct.

## End-to-End Workflow

```bash
# 1. Create MCP config file (one-time setup)
cat > orca/assets/mcp_config.json <<EOF
{
  "type": "http",
  "url": "https://orcaservices-360095844563.us-central1.run.app",
  "headers": {
    "X-API-KEY": "your-api-key-here"
  }
}
EOF

# 2. Install MCP SDK (if not already installed)
pip install mcp

# 3. Run the metadata creation script
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config orca/assets/mcp_config.json

# 4. If interrupted, simply re-run the same command (checkpoint resume)
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config orca/assets/mcp_config.json

# 5. Verify a sample entry
# (call list_rag_metadata for a specific ragFileName)
```

### Script Output

The script prints progress information:
- Number of included regulations found
- Number of document matches
- Batch processing progress
- Success/failure counts per batch
- Final summary with success rate and failure details

## Related Scripts

### bulk_create_rag_metadata.py

Legacy script for processing pre-generated batch files. The new `create_rag_jurisdiction_metadata.py` replaces this workflow by integrating data fetching, matching, and processing into a single script.

For detailed documentation on the legacy approach, see `orca/scripts/BULK_PROCESSING_GUIDE.md`.

## Key Takeaways

1. **Use MCP SDK for efficiency**: The script calls MCP tools directly via the Python SDK, avoiding agent token costs and reasoning overhead for batch operations.
2. **Only process included regulations**: The script filters for `included: true` to avoid metadata on irrelevant files.
3. **Checkpoint-based resumption**: Progress tracks batch file name and index position. If interrupted, simply re-run the same command to resume from the exact position.
4. **Handle false negatives**: The script detects INTERNAL errors and verifies success via `list_rag_metadata` to handle false negative responses from `create_rag_metadata`.
5. **Verify-as-you-go**: Every create/update operation is immediately verified to ensure data integrity.
6. **Avoid duplicate writes**: The script checks existing metadata before writing to prevent timeout errors from creating metadata on an existing key.
7. **Intermediate batch files**: Batch files are saved to `orca/assets/` for debugging and audit purposes.
8. **Batch size optimized**: Uses batch size of 100 for optimal performance with `create_rag_metadata` operations.
9. **Always validate**: Review the final summary and spot-check failed entries to ensure completeness.
10. **Batch files as work units**: Intermediate batch files in `orca/assets/` are the primary processing units, enabling easy inspection and debugging of the matching logic.
