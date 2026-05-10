# Document RAG File Matching Report

## Overview

This skill describes how to generate a comprehensive HTML report that matches documents in a repository against RAG files in the corresponding corpus. The report identifies unmatched documents, documents with missing `rag_file_name`, correctly matched documents, and documents with incorrect `rag_file_name` values. It also provides guidance on batch-resolving mismatches.

## Prerequisites

- Access to the Orca MCP server
- The following tools: `list_corpus`, `list_rag_files`, `list_workspaces`, `list_repositories`, `list_documents`, `set_rag_file_name`

## Step 1: Fetch Data

### 1.1 Identify the Target Corpus

If you know the corpus display name (e.g., `prod-s30-w1-r6-happy-quartz`), call `list_corpus` to find its full resource name:

```bash
# Call list_corpus MCP tool
# Response includes: displayName, name (full resource path)
```

Extract the `name` field for the target corpus. Example:
```
projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088
```

### 1.2 Fetch RAG Files

Call `list_rag_files` with the corpus `name`:

```json
{
  "corpusName": "projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088"
}
```

**Cache the response** in `orca/cache/` per the caching policy in `orca/AGENTS.md`.

### 1.3 Find Workspace and Repository IDs

Call `list_workspaces` to get all workspaces, then `list_repositories` for each workspace until you find the repository whose `corpus_name` matches the target corpus.

Example workflow:
```bash
# Call list_workspaces
# For each workspace, call list_repositories with workspaceId
# Find the repository where corpus_name == target_corpus_name
# Note the workspaceId and repositoryId
```

### 1.4 Fetch Documents

Call `list_documents` with the resolved `workspaceId` and `repositoryId`:

```json
{
  "workspaceId": 1,
  "repositoryId": 6,
  "limit": 10000
}
```

**Cache the response** in `orca/cache/`.

---

## Step 2: Analyze & Match

Use the script `orca/scripts/generate_document_rag_file_report.py` to perform matching and generate the report.

### Script Usage

```bash
python3 orca/scripts/generate_document_rag_file_report.py <path_to_documents_cache> <path_to_rag_files_cache> [output_file]
```

**Parameters:**
- `path_to_documents_cache` (required): Path to the cached `list_documents` JSON response.
- `path_to_rag_files_cache` (required): Path to the cached `list_rag_files` JSON response.
- `output_file` (optional): Output HTML file path. Defaults to `document_rag_file_report.html`.

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

The `set_rag_file_name` MCP tool only supports single-document updates. To process multiple documents efficiently:

1. **Extract the list of documents to update** from the report or the script's intermediate output.
2. **Loop over the list** in batches of 10–20 documents per iteration.
3. **Call `set_rag_file_name`** for each document:

```json
{
  "workspaceId": 1,
  "documentId": 780,
  "ragFileName": "projects/360095844563/locations/us-east4/ragCorpora/3419358017081049088/ragFiles/5685605325190625475"
}
```

4. **Monitor progress**: Track successful updates and log any errors.

### Recommended Approach

For large datasets (1000+ documents), consider writing a small Python script that:
- Reads the list of documents to update from a JSON file.
- Calls the `set_rag_file_name` MCP tool in a loop with a delay between calls (e.g., 0.5 seconds) to avoid rate limiting.
- Logs progress and errors to a file.

Example pseudo-code:
```python
import time
import json

with open("documents_to_update.json") as f:
    updates = json.load(f)

for i, doc in enumerate(updates):
    # Call set_rag_file_name MCP tool
    result = call_mcp_tool("set_rag_file_name", {
        "workspaceId": doc["workspaceId"],
        "documentId": doc["documentId"],
        "ragFileName": doc["ragFileName"]
    })
    
    if i % 10 == 0:
        print(f"Processed {i+1}/{len(updates)} documents")
    
    time.sleep(0.5)  # Rate limiting
```

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
python3 orca/scripts/generate_document_rag_file_report.py \
  orca/cache/orca_cache_{new_docs_hash}.json \
  orca/cache/orca_cache_970ee63a14ba2333.json \
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

The Python script at `orca/scripts/generate_document_rag_file_report.py` automates Steps 2 and 3 (analysis + HTML generation).

### End-to-End Workflow

```bash
# 1. Fetch data via MCP tools and save to cache files
# (call list_rag_files, list_documents, etc., save outputs to orca/cache/)

# 2. Generate the initial report
python3 orca/scripts/generate_document_rag_file_report.py \
  orca/cache/orca_cache_1121a24f496f7fbc.json \
  orca/cache/orca_cache_970ee63a14ba2333.json

# 3. Open the initial report
open document_rag_file_report.html

# 4. Review the report and extract documents needing updates
# 5. Run batch updates using the recommended workflow above

# 6. Re-fetch documents to verify updates
# (call list_documents again, save to a new cache file)

# 7. Generate verification report
python3 orca/scripts/generate_document_rag_file_report.py \
  orca/cache/orca_cache_{new_docs_hash}.json \
  orca/cache/orca_cache_970ee63a14ba2333.json \
  document_rag_file_report_verification.html

# 8. Open and review the verification report
open document_rag_file_report_verification.html
```

The script handles all analysis logic — matching documents to RAG files, classifying by status, computing summary statistics, and generating the full Gmail-compatible HTML report with inline styles.

---

## Key Takeaways

1. Always match documents to RAG files by comparing `document.filename` with `rag_file.displayName`.
2. Use the script to automate analysis and report generation; do not manually inspect large datasets.
3. The HTML report is designed for Gmail compatibility — use inline CSS and table-based layouts.
4. Batch resolution requires looping over individual `set_rag_file_name` calls; implement rate limiting for large datasets.
5. Cache all MCP tool responses to avoid redundant API calls and improve performance.
