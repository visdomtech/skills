# Create RAG Jurisdiction Metadata

## Overview

This skill describes how to create `jurisdiction_code` metadata for RAG files by matching included regulations to their corresponding documents in the Compliance Repository. This ensures that RAG search results can be filtered or boosted by jurisdiction.

## Prerequisites

- Access to the Orca MCP server
- The following tools: `list_regulations`, `list_documents`, `create_rag_metadata`, `update_rag_metadata`, `list_rag_metadata`
- Well-known data: Workspace 1, Compliance Repository ID 6

## Step 1: Fetch Data

### 1.1 Fetch Included Regulations

Call `list_regulations` with `workspaceId=1` and `limit=2147483647`. Filter the response to keep only entries where `included: true`.

**Save the response** in `orca/assets/` as `workspace_1_included_regulations.json`.

### 1.2 Fetch Compliance Documents

Call `list_documents` with `workspaceId=1`, `repositoryId=6`, and `limit=2147483647`.

**Save the response** in `orca/assets/` as `workspace_1_repo_6_documents.json`.

## Step 2: Match and Create Metadata

Use the script `orca/scripts/create_rag_jurisdiction_metadata.py` to perform matching and generate batched payloads.

### Script Usage

```bash
python3 orca/scripts/create_rag_jurisdiction_metadata.py <path_to_regulations_cache> <path_to_documents_cache>
```

**Parameters:**
- `path_to_regulations_cache` (required): Path to the cached `list_regulations` JSON response.
- `path_to_documents_cache` (required): Path to the cached `list_documents` JSON response.

### Batch Generation Logic

The script performs the following:
1. **Iterate over included regulations**: For each regulation, extract its `filenames` and `jurisdiction.code`.
2. **Find matching documents**: Look for documents in the cache whose `filename` matches any of the regulation's filenames.
3. **Generate Batches**: Group the matches into batches of 200. For each batch, create a JSON file structured for the `create_rag_metadata` tool:
   ```json
   {
     "files": [
       {
         "ragFileName": "projects/.../ragFiles/...",
         "entries": [
           { "key": "jurisdiction_code", "valueStr": "US" }
         ]
       }
     ]
   }
   ```

## Step 3: Agent Execution

The agent is responsible for invoking the MCP tools for each entry in the generated batch files.

### Checkpoint-Based Resumption

**CRITICAL**: Always read `orca/assets/rag_meta_batch_progress.json` before starting to determine where to resume:

```json
{
  "current_batch": "rag_meta_batch_4.json",
  "current_batch_index": 0,
  "completed_entries": 700,
  "total_entries": 1347,
  "last_updated": "2026-05-11T21:30:00Z"
}
```

**Resume Logic:**
1. Read the progress file to get `current_batch` and `current_batch_index`
2. Load that specific batch file (e.g., `rag_meta_batch_4.json`)
3. Start processing from index `current_batch_index` (not from 0)
4. Update the progress file after every 10-20 entries processed
5. When a batch is complete, advance to the next batch file and reset index to 0

**Example Resume Flow:**
- Progress shows: batch=`rag_meta_batch_3.json`, index=100
- Load `rag_meta_batch_3.json` 
- Process entries starting at index 100 (skip indices 0-99)
- After processing entry 100, update progress to index=101
- Continue until end of batch, then move to next batch

### Processing Steps

1. **Read Batch Files**: For each batch file, read the JSON and iterate through the `files` array starting from `current_batch_index`.
2. **Check Existing Metadata**: Before creating or updating, call `list_rag_metadata` for the target `ragFileName` to check if the metadata key already exists.
3. **Decision Logic**:
   - **If the key is missing**: Call `create_rag_metadata` with the entry's `ragFileName` and `entries` fields.
   - **If the key exists and the value is identical**: Skip this entry (no action needed).
   - **If the key exists but the value is different**: Call `update_rag_metadata` with the entry's `ragFileName` and `entries` fields.
4. **Immediate Verification**: After a successful creation or update, immediately invoke `list_rag_metadata` for the same `ragFileName`.
5. **Validate Result**: Compare the returned metadata with the expected values from the `entries` field.
6. **Track Progress**: Log the result of both the operation and verification (e.g., "Created & Verified", "Updated & Verified", "Skipped (Match)", or "Failed/Mismatch").
7. **Update Progress File**: After processing each batch of entries (recommended every 10-20 entries), update the progress tracking file at `orca/assets/rag_meta_batch_progress.json` with the current state. This ensures resumability if the process is interrupted.

**Important**: Always check existing metadata using `list_rag_metadata` before attempting to create. Creating metadata on an existing key can cause timeouts. If the value differs, use `update_rag_metadata` instead.

**Performance Note**: Processing entries one-by-one via MCP tool calls is slow (~2-3 seconds per entry). For large batches (100+ entries), consider sampling to verify completion status before exhaustive processing. If most entries already have correct metadata from a previous session, you may be able to mark the batch as complete after verifying representative samples across all jurisdiction groups.

### Example Tool Call Sequence

**1. Check Metadata:**
```json
{
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5620287928265909657"
}
```

**2a. Create Metadata (if key is missing):**
```json
{
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5620287928265909657",
  "entries": [
    { "key": "jurisdiction_code", "valueStr": "US" }
  ]
}
```

**2b. Update Metadata (if key exists with different value):**
```json
{
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5620287928265909657",
  "entries": [
    { "key": "jurisdiction_code", "valueStr": "US" }
  ]
}
```

**3. Verify Metadata:**
```json
{
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5620287928265909657"
}
```

Note: Both `create_rag_metadata` and `update_rag_metadata` support multiple metadata keys (`entries`) for a single file, but each call only targets one file. The agent must call the tool once per file.

### 3.1 Sample Check

After the script completes, pick a few updated RAG file names and call `list_rag_metadata` to confirm the `jurisdiction_code` is present.

```json
{
  "ragFileName": "projects/.../ragFiles/..."
}
```

### 3.2 Count Validation

Compare the number of successful `create_rag_metadata` calls reported by the script with the number of matched regulations. They should be equal.

## Automated Script

A Python script at `orca/scripts/create_rag_jurisdiction_metadata.py` automates Steps 2 and 3 (matching + metadata creation).

### End-to-End Workflow

```bash
# 1. Fetch data via MCP tools and save to assets files
# (call list_regulations and list_documents, save outputs to orca/assets/)

# 2. Run the metadata creation script
python3 orca/scripts/create_rag_jurisdiction_metadata.py \
  orca/assets/workspace_1_included_regulations.json \
  orca/assets/workspace_1_repo_6_documents.json

# 3. Verify a sample entry
# (call list_rag_metadata for a specific ragFileName)
```

## Bulk Processing Scripts

For processing large volumes of entries efficiently, use the bulk processing scripts:

### bulk_create_rag_metadata.py

Processes all batch files by invoking MCP tools for each entry.

**Usage:**
```bash
# Dry run first (recommended)
python3 orca/scripts/bulk_create_rag_metadata.py --dry-run --limit 5

# Process with verification
python3 orca/scripts/bulk_create_rag_metadata.py --verify --limit 100

# Resume from specific batch
python3 orca/scripts/bulk_create_rag_metadata.py --start-from rag_meta_batch_2.json

# Process all remaining entries
python3 orca/scripts/bulk_create_rag_metadata.py
```

**Options:**
- `--dry-run`: Test without making changes
- `--verify`: Enable immediate verification after each creation
- `--limit N`: Process only N entries (for testing)
- `--start-from FILE`: Resume from a specific batch file
- `--batch-dir DIR`: Directory containing batch files (default: ../assets)
- `--progress-file FILE`: Path to progress tracking file (default: ../assets/rag_meta_batch_progress.json)

**Progress Tracking**: The script automatically tracks progress in `rag_meta_batch_progress.json`. After each entry is processed, the progress file is updated with:
- Current batch file being processed
- Current index within the batch
- Total completed entries
- Last updated timestamp

This enables automatic resumption from the last checkpoint if the process is interrupted.

### verify_rag_metadata.py

Verifies that metadata was correctly created.

**Usage:**
```bash
# Verify a random sample
python3 orca/scripts/verify_rag_metadata.py --sample 50

# Verify all entries
python3 orca/scripts/verify_rag_metadata.py --full
```

**Options:**
- `--sample N`: Verify a random sample of N entries
- `--full`: Verify all entries
- `--batch-dir DIR`: Directory containing batch files
- `--report FILE`: Output file for verification report

For detailed documentation, see `orca/scripts/BULK_PROCESSING_GUIDE.md`.

## Key Takeaways

1. **Only process included regulations**: Filter for `included: true` to avoid metadata on irrelevant files.
2. **Use scripts for efficiency**: The automation scripts handle large volumes of regulations and documents efficiently.
3. **Verify-as-you-go pattern**: For critical operations, use immediate verification after each metadata creation.
4. **Bulk processing available**: Use `bulk_create_rag_metadata.py` for efficient batch processing with optional verification.
5. **Checkpoint-based resumption**: ALWAYS read `rag_meta_batch_progress.json` first to determine which batch file and which index to start from. Never restart from index 0 unless explicitly instructed.
6. **Periodic progress updates**: Update the progress file after every 10-20 entries to minimize data loss on interruption.
7. **Always validate**: Use `list_rag_metadata` or `verify_rag_metadata.py` to ensure data integrity.
8. **Handle false negatives**: The `create_rag_metadata` tool may return `Internal` errors even when the operation succeeds. Always verify with `list_rag_metadata` after creation attempts.
9. **Sampling for efficiency**: When resuming a batch, sample entries across different jurisdictions to check if they were already processed in a previous session. If all samples show correct metadata, the batch may already be complete.
