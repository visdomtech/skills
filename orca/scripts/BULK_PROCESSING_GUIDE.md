# Bulk RAG Metadata Processing Guide

This guide explains how to use the bulk processing scripts to create and verify jurisdiction_code metadata for RAG files.

## Overview

The bulk processing workflow consists of three main steps:

1. **Generate Batch Files**: Use `create_rag_jurisdiction_metadata.py` to match regulations with documents and generate batch files
2. **Process Batches**: Use `bulk_create_rag_metadata.py` to invoke MCP tools for each entry
3. **Verify Results**: Use `verify_rag_metadata.py` to confirm metadata was created correctly

## Prerequisites

- Python 3.6+
- Access to Orca MCP server
- Cached regulation and document data in `orca/assets/`

## Step 1: Generate Batch Files

```bash
python3 orca/scripts/create_rag_jurisdiction_metadata.py \
  orca/assets/workspace_1_regulations.json \
  orca/assets/workspace_1_repo_6_documents.json
```

This will generate batch files like:
- `orca/assets/rag_meta_batch_1.json` (200 entries)
- `orca/assets/rag_meta_batch_2.json` (200 entries)
- ... etc.

## Step 2: Process Batches

### Option A: Dry Run (Recommended First)

Test what would be processed without making changes:

```bash
python3 orca/scripts/bulk_create_rag_metadata.py --dry-run
```

### Option B: Process All Entries

Process all entries from all batch files:

```bash
python3 orca/scripts/bulk_create_rag_metadata.py
```

### Option C: Process with Verification

Enable immediate verification after each creation:

```bash
python3 orca/scripts/bulk_create_rag_metadata.py --verify
```

### Option D: Resume from Specific Batch

If you need to resume from a specific batch file:

```bash
python3 orca/scripts/bulk_create_rag_metadata.py --start-from rag_meta_batch_3.json
```

### Option E: Limit Processing (for testing)

Process only a limited number of entries:

```bash
python3 orca/scripts/bulk_create_rag_metadata.py --limit 50
```

## Step 3: Verify Results

### Option A: Sample Verification

Verify a random sample of entries:

```bash
python3 orca/scripts/verify_rag_metadata.py --sample 50
```

### Option B: Full Verification

Verify all entries (may take a long time):

```bash
python3 orca/scripts/verify_rag_metadata.py --full
```

## Understanding the Scripts

### create_rag_jurisdiction_metadata.py

**Purpose**: Matches included regulations to documents and generates batch files.

**Input**:
- Regulations JSON cache
- Documents JSON cache

**Output**:
- Batch files (`rag_meta_batch_*.json`) containing matched entries

**Key Logic**:
1. Filters regulations where `included=true`
2. Matches regulation filenames to document filenames
3. Groups matches into batches of 200
4. Generates JSON structured for MCP tool calls

### bulk_create_rag_metadata.py

**Purpose**: Processes batch files by invoking MCP tools.

**Features**:
- Reads all batch files from the assets directory
- Calls `create_rag_metadata` for each entry
- Supports dry-run mode for testing
- Supports immediate verification (--verify flag)
- Generates processing report

**Note**: The script currently simulates MCP tool calls. To make it functional, replace the TODO comments with actual `CallMcpTool` invocations.

### verify_rag_metadata.py

**Purpose**: Verifies that metadata was correctly created.

**Features**:
- Supports random sampling or full verification
- Compares expected vs actual metadata values
- Generates detailed verification report

**Note**: Like the bulk processing script, this currently simulates verification. Replace TODO comments with actual `list_rag_metadata` calls.

## Reports

Both scripts generate JSON reports:

- **bulk_processing_report.json**: Summary of processing results
- **verification_report.json**: Detailed verification results

Example report structure:

```json
{
  "summary": {
    "total_entries": 1347,
    "processed": 1347,
    "failed": 0,
    "remaining": 0,
    "success_rate": "100.00%"
  }
}
```

## Troubleshooting

### No batch files found

Ensure you've run `create_rag_jurisdiction_metadata.py` first and that the batch files exist in `orca/assets/`.

### Script hangs or takes too long

- Use `--limit` to process fewer entries for testing
- Use `--dry-run` to verify the script works without making changes
- Consider processing in smaller batches using `--start-from`

### Verification fails

- Check that the MCP server is accessible
- Verify the `ragFileName` format is correct
- Ensure the corpus ID matches your workspace

## Best Practices

1. **Always dry-run first**: Test with `--dry-run` before processing real data
2. **Start small**: Use `--limit 10` to test with a small sample
3. **Enable verification**: Use `--verify` for critical operations
4. **Save reports**: Keep the generated reports for auditing
5. **Resume capability**: If interrupted, use `--start-from` to continue

## Example Workflow

```bash
# 1. Generate batches
python3 orca/scripts/create_rag_jurisdiction_metadata.py \
  orca/assets/workspace_1_regulations.json \
  orca/assets/workspace_1_repo_6_documents.json

# 2. Dry run to verify
python3 orca/scripts/bulk_create_rag_metadata.py --dry-run --limit 5

# 3. Process with verification (first 50 entries)
python3 orca/scripts/bulk_create_rag_metadata.py --verify --limit 50

# 4. Continue processing remaining entries
python3 orca/scripts/bulk_create_rag_metadata.py --start-from rag_meta_batch_1.json

# 5. Verify a sample
python3 orca/scripts/verify_rag_metadata.py --sample 100
```

## Next Steps

To make these scripts fully functional:

1. Replace the TODO comments in `bulk_create_rag_metadata.py` with actual MCP tool calls
2. Replace the TODO comments in `verify_rag_metadata.py` with actual verification calls
3. Add error handling and retry logic for failed calls
4. Add logging to track progress across sessions

For now, these scripts serve as templates and documentation for the bulk processing workflow.
