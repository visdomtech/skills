# Document RAG File Matching Report

## Overview

This skill describes how to generate a comprehensive HTML report that matches documents in a repository against RAG files in the corresponding corpus. The report identifies unmatched documents, documents with missing `rag_file_name`, correctly matched documents, and documents with incorrect `rag_file_name` values. It also provides guidance on batch-resolving mismatches.

## Prerequisites

- Access to the Orca MCP server
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- MCP config JSON

## Step 1: Fetch Data

Run the fetch script, which calls all required MCP tools via the MCP SDK and generates the report automatically.

```bash
# Prepare virtual environment
cd orca
uv sync
source .venv/bin/activate

# Fetch data and generate report (default corpus: prod-s30-w1-r6-happy-quartz)
uv run fetch-document-rag-data --config orca/assets/mcp_config.json

# Specify a different corpus
uv run fetch-document-rag-data \
  --config orca/assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r5-agile-wave \
  --output orca/assets/policy_rag_file_report.html
```

**Arguments:**
- `--config` (required): Path to MCP config JSON
- `--corpus-display-name` (optional): Corpus display name. Default: `prod-s30-w1-r6-happy-quartz`
- `--output` (optional): Output HTML path. Default: `orca/assets/document_rag_file_report.html`

**MCP config format** (`orca/assets/mcp_config.json`):
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
1. Calls `list_corpus` to resolve the corpus resource name
2. Calls `list_rag_files` with the resolved corpus name
3. Calls `list_workspaces` + `list_repositories` to find the matching workspace/repository
4. Calls `list_documents` with the resolved IDs
5. Saves RAG files to `orca/assets/rag_files.json` and documents to `orca/assets/documents.json`
6. Runs `generate_document_rag_file_report.py` to produce the HTML and CSV outputs

---

## Step 2: Analyze & Match

Use the script `orca/scripts/document_rag_file_report/generate_document_rag_file_report.py` to perform matching and generate the report.

### Script Usage

```bash
python3 orca/scripts/document_rag_file_report/generate_document_rag_file_report.py <path_to_documents_cache> <path_to_rag_files_cache> [output_file]
```

**Parameters:**
- `path_to_documents_cache` (required): Path to the cached `list_documents` JSON response.
- `path_to_rag_files_cache` (required): Path to the cached `list_rag_files` JSON response.
- `output_file` (optional): Output HTML file path. Defaults to `document_rag_file_report.html`. A corresponding CSV file (`document_rag_file_report.csv`) will also be generated containing all actionable items.

### Matching Logic

The script performs the following analysis:

1. **Build RAG lookup map**: Creates a dictionary mapping `rag_file.displayName` → `rag_file.name`.
2. **Iterate over documents**: For each document, check if `document.filename` exists in the RAG lookup map.
3. **Classify each document** into one of four categories:

| Category | Criteria |
|----------|----------|
| **Unmatched** | No RAG file has a `displayName` matching the document's `filename`. |
| **Matched — Empty/Null** | A matching RAG file exists, but `document.rag_file_name` is `null` or empty string. |
| **Matched — Correct** | A matching RAG file exists, and `document.rag_file_name` equals the RAG file's `name`. |
| **Matched — Different** | A matching RAG file exists, but `document.rag_file_name` is set to a different value. |

4. **Generate summary statistics**: Total counts and percentages for each category.
5. **Export actionable items**: A CSV file is automatically generated containing all documents with "Empty/Null" or "Different" statuses, ready for batch processing.

---

## Step 3: Generate HTML Report

The script generates a Gmail-compatible HTML report with inline CSS and table-based layout. The report follows the same professional design pattern as the jurisdictions report.

### Report Sections

#### Hero Header
- Repository name and corpus display name.
- Generation timestamp.

#### Summary Metrics Bar
- Total documents count.
- Unmatched count.
- Matched counts broken down by status (Empty/Null, Correct, Different).

#### Status Distribution Cards
Four color-coded cards showing counts and percentages:
- **Unmatched** — Gray theme (`#f1f5f9` background, `#475569` text)
- **Empty/Null** — Amber theme (`#fffbeb` background, `#b45309` text)
- **Correct** — Green theme (`#f0fdf4` background, `#15803d` text)
- **Different** — Red theme (`#fef2f2` background, `#dc2626` text)

#### Detail Tables
One section per category. For large lists (>20 items), the report shows:
- First 20 entries.
- Last 20 entries.
- A "... N more ..." indicator in between.

Each row displays:
- Document ID (monospace font).
- Filename (bold).
- Current `rag_file_name` (if any, monospace, truncated if long).
- Matching RAG file `name` (monospace, truncated if long).

#### Status Legend
A dedicated legend section explaining the color coding for each status badge.

#### Footer
- Report name and generator attribution.
- Confidentiality notice.

---

## Step 4: Batch Resolution

After reviewing the report, resolve all documents that need `rag_file_name` updates.

### Documents to Process

1. **All "Matched — Empty/Null" documents**: Set `rag_file_name` to the matching RAG file's `name`.
2. **All "Matched — Different" documents**: Update `rag_file_name` to the correct matching RAG file's `name`.

### Batch Update Workflow

The skill provides a dedicated script `orca/scripts/document_rag_file_report/batch_update_rag_file_name.py` that reads the generated CSV and calls `set_rag_file_name` directly via the MCP SDK in optimized batches.

1. **Use the provided script**: Run the script with the path to the generated CSV file:
   ```bash
   uv run python3 orca/scripts/document_rag_file_report/batch_update_rag_file_name.py \
     --config orca/assets/mcp_config.json \
     --csv orca/assets/document_rag_file_report.csv \
     [--workspace-id <id>]
   ```
   
   The `--workspace-id` parameter is optional. If not specified, it defaults to workspace ID 1. For other workspaces, specify the correct ID (e.g., `--workspace-id 2`).

2. **Batch Configuration**: The script is configured to use a batch size of **200** entries per call to maximize throughput while respecting API limits.
3. **Monitor progress**: The script outputs per-batch progress and a final summary of successful and failed updates.

---

## Step 5: Verification

After completing the batch updates, verify that all `rag_file_name` values were properly set.

### 5.1 Re-fetch Documents

Call `list_documents` again with the same `workspaceId` and `repositoryId`:

```json
{
  "workspaceId": 1,
  "repositoryId": 6,
  "limit": 10000
}
```

**Cache the new response** as a new cache file (e.g., `orca_cache_{new_hash}.json`) to avoid overwriting the pre-update data. This allows you to keep both the before and after snapshots for comparison.

### 5.2 Re-run the Report Script

Generate a new report using the updated documents cache and the original RAG files cache:

```bash
python3 orca/scripts/document_rag_file_report/generate_document_rag_file_report.py \
  orca/assets/orca_cache_{new_docs_hash}.json \
  orca/assets/orca_cache_970ee63a14ba2333.json \
  document_rag_file_report_verification.html
```

### 5.3 Verify Results

Open the new report and confirm the following:

| Metric | Before Update | After Update | Expected Change |
|--------|---------------|--------------|-----------------|
| **Matched — Empty/Null** | N | 0 | Should be zero |
| **Matched — Different** | M | 0 | Should be zero |
| **Matched — Correct** | C | C + N + M | Should increase by the number of documents updated |
| **Unmatched** | U | U | Should remain unchanged |

### 5.4 Handle Discrepancies

If any documents still appear in the "Empty/Null" or "Different" categories after verification:

1. **Check for API failures**: Review logs from the batch update process for any `set_rag_file_name` errors.
2. **Check for rate limiting**: If errors mention rate limiting or timeouts, retry the updates with a longer delay between calls.
3. **Check for concurrent modifications**: Another process may have modified the documents between your update and verification fetches. Re-fetch and re-verify.
4. **Investigate edge cases**: Documents with special characters in filenames or very long filenames may fail silently. Manually inspect any remaining mismatches.

---

## Automated Script

The Python script at `orca/scripts/document_rag_file_report/generate_document_rag_file_report.py` automates Steps 2 and 3 (analysis + HTML generation).

### End-to-End Workflow

```bash
# 1. Fetch all data and generate initial report
cd orca && uv sync && source .venv/bin/activate
uv run fetch-document-rag-data --config orca/assets/mcp_config.json

# 2. Open the initial report
open orca/assets/document_rag_file_report.html

# 3. Review the report and run batch updates from the generated CSV
uv run python3 orca/scripts/document_rag_file_report/batch_update_rag_file_name.py \
  --config orca/assets/mcp_config.json \
  --csv orca/assets/document_rag_file_report.csv

# 4. Re-fetch to verify updates and generate verification report
uv run fetch-document-rag-data \
  --config orca/assets/mcp_config.json \
  --output orca/assets/document_rag_file_report_verification.html

# 5. Open and review the verification report
open orca/assets/document_rag_file_report_verification.html
```

`generate_document_rag_file_report.py` handles all analysis logic — matching documents to RAG files, classifying by status, computing summary statistics, and generating the full Gmail-compatible HTML report with inline styles.

---

## Key Takeaways

1. Always match documents to RAG files by comparing `document.filename` with `rag_file.displayName`.
2. Use the script to automate analysis and report generation; do not manually inspect large datasets.
3. The generated CSV file provides a direct source for batch updates, eliminating manual data extraction.
4. The HTML report is designed for Gmail compatibility — use inline CSS and table-based layouts.
5. Batch resolution should use the `entries` array in `set_rag_file_name` with a batch size of **200** for optimal efficiency.
6. Save all MCP tool responses in `orca/assets/` to facilitate reuse and avoid redundant API calls.
