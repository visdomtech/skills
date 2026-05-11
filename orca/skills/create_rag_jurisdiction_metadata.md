# Create RAG Jurisdiction Metadata

## Overview

Creates `jurisdiction_code` metadata for RAG files by matching included regulations to documents in the Compliance Repository. This enables jurisdiction-based filtering and boosting in RAG search results.

## Prerequisites

- Orca MCP server access
- MCP Python SDK: `pip install mcp`
- MCP config JSON (see Step 1)
- Tools used: `list_regulations`, `list_documents`, `create_rag_metadata`, `update_rag_metadata`, `list_rag_metadata`
- Workspace 1, Compliance Repository ID 6

## Step 1: Prepare MCP Config

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

Save as `orca/assets/mcp_config.json`. **Never commit API keys.**

## Step 2: Run the Script

The script automates the entire workflow:

1. Fetches included regulations (`list_regulations`)
2. Fetches compliance documents (`list_documents`)
3. Matches regulations to documents by filename
4. Saves intermediate batch files to `orca/assets/`
5. Creates/updates `jurisdiction_code` metadata with verification
6. Handles false-negative INTERNAL errors
7. Tracks progress for checkpoint resumption

### Usage

```bash
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config <path_to_mcp_config.json>
```

**Parameters:**
- `--config` (required): Path to MCP config JSON.

## Step 3: Checkpoint Resumption

Progress is tracked in `orca/assets/rag_meta_batch_progress.json`:

```json
{
  "current_batch": "rag_meta_batch_4.json",
  "current_batch_index": 0,
  "completed_entries": 700,
  "total_entries": 1347,
  "last_updated": "2026-05-11T21:30:00Z"
}
```

**Resume behavior:**
- Re-run the same command after interruption
- Skips completed batches, resumes at `current_batch_index`
- Progress saved every 10 entries
- Index resets to 0 when advancing to next batch

## Error Handling

### False-Negative INTERNAL Errors

`create_rag_metadata` often returns `INTERNAL` errors even on success. The script:

1. Detects INTERNAL errors
2. Verifies via `list_rag_metadata`
3. Treats as success if metadata appears
4. Logs as "Created & Verified (false negative)"

### Decision Logic

Before writing, the script checks existing state:

- **Key missing** → `create_rag_metadata`
- **Key matches** → Skip
- **Key differs** → `update_rag_metadata`

This prevents timeout errors from duplicate creates.

### Verification

Every create/update is verified immediately via `list_rag_metadata`.

## Verification

### Sample Check

Call `list_rag_metadata` for a few RAG files to confirm `jurisdiction_code` exists.

### Count Validation

Compare processed entries to total matched regulations (minus legitimate failures).

### Batch Files

Intermediate batches in `orca/assets/` can be inspected to verify matching logic.

## Workflow

```bash
# 1. Create MCP config (one-time)
cat > orca/assets/mcp_config.json <<EOF
{
  "type": "http",
  "url": "https://orcaservices-360095844563.us-central1.run.app",
  "headers": {"X-API-KEY": "your-api-key-here"}
}
EOF

# 2. Install SDK
pip install mcp

# 3. Run script
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config orca/assets/mcp_config.json

# 4. Resume if interrupted (same command)
python3 orca/scripts/create_rag_jurisdiction_metadata.py --config orca/assets/mcp_config.json
```

### Output

The script prints:
- Included regulations found
- Document matches
- Batch progress
- Final summary with success rate

## Key Takeaways

1. **MCP SDK efficiency**: Direct tool calls avoid agent overhead
2. **Included regulations only**: Filters `included: true`
3. **Checkpoint resumption**: Batch name + index tracking
4. **False-negative handling**: Verifies INTERNAL errors
5. **Verify-as-you-go**: Immediate post-operation checks
6. **No duplicate writes**: Checks before creating
7. **Batch files in assets**: Debugging and audit trail
8. **Batch size 200**: Optimized for performance
9. **Validate results**: Review summary and failures
10. **Batch files as units**: Easy inspection of matching logic
