# RAG Jurisdiction Metadata Report

## Overview

This skill describes how to generate a comprehensive report on the jurisdiction metadata associated with documents in the `prod-s30-w1-r6-happy-quartz` compliance repository. The process uses the Python MCP SDK to fetch metadata for each document in parallel and produces two outputs:
1. A detailed CSV file containing all metadata entries for every document.
2. An HTML summary report highlighting jurisdiction distribution and identifying documents missing jurisdiction metadata.

**Firestore Caching**: The script now supports Firestore caching to avoid expensive individual API calls to Vertex corpus (which doesn't support batching). On first run, metadata is fetched from MCP and cached in Firestore. Subsequent runs use cached data by default, dramatically improving performance.

## Prerequisites

- Access to the Orca MCP server.
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`).
- **Optional**: Google Cloud credentials configured for Firestore access (for caching).
- Workspace ID: 1, Repository ID: 6.

## Step 1: Prepare Documents Data

Before running the report, ensure the documents cache is up-to-date:

```bash
cd orca
uv run fetch-compliance-documents --config assets/mcp_config.json
```

This generates `assets/compliance_documents.json`, which is required by the report script.

## Step 2: Prepare Environment

Before running the script, ensure your virtual environment is set up and dependencies are installed:

```bash
cd orca
uv sync
```

## Step 2: Run the Script

Execute the generation script using your MCP configuration:

```bash
# Default: Uses Firestore cache if available
uv run rag-metadata-report --config assets/mcp_config.json

# Force refresh from MCP (ignore cache)
uv run rag-metadata-report --config assets/mcp_config.json --force-refresh
```

The script will:
1. Load the list of documents from `assets/compliance_documents.json`.
2. Connect to the Orca MCP server.
3. **Check Firestore cache** for each document's metadata (unless `--force-refresh` is used).
4. Fetch missing metadata from MCP in parallel (concurrency limit: 3).
5. **Cache fetched metadata in Firestore** for future use.
6. Generate `assets/rag_metadata_report.csv` with detailed metadata.
7. Generate `assets/rag_metadata_summary.html` with a visual summary.

## Output Files

### 1. Detailed CSV (`rag_metadata_report.csv`)
Contains one row per metadata entry. If a document has multiple metadata keys, it will have multiple rows.

| Column | Description |
| :--- | :--- |
| `filename` | The name of the compliance document. |
| `rag_file_name` | The full resource name of the associated RAG file. |
| `uploaded` | The UTC timestamp when the document was uploaded (`uploaded_at` from the document record). |
| `metadata_key` | The key of the metadata entry (e.g., `jurisdiction_code`). |
| `metadata_value` | The value of the metadata entry. |

### 2. Summary HTML (`rag_metadata_summary.html`)
A professional, Gmail-compatible HTML report containing:
- **Summary Metrics**: Total documents, count with jurisdiction metadata, and count without.
- **Jurisdiction Distribution**: A table showing the number of documents grouped by their `jurisdiction_code`.
- **Missing Metadata List**: A list of filenames that do not have a `jurisdiction_code` metadata entry.

## Implementation Details

- **Parallel Processing**: The script uses `asyncio.Semaphore` to limit concurrent API calls, ensuring high performance without overwhelming the MCP server.
- **Firestore Caching**: Metadata is cached in Firestore collection `rag_metadata_cache` using the RAG file ID as the document key. This avoids repeated expensive API calls.
- **Cache Strategy**: Firestore-first approach - checks cache before calling MCP, updates cache after fetching.
- **Error Handling**: If metadata fetching fails for a specific document, the error is logged and recorded in the CSV, but processing continues for other documents. Failed attempts are also cached to prevent repeated failures.
- **Progress Tracking**: The script prints progress updates to the console (e.g., "Processed 50/1300 documents...").
- **Graceful Fallback**: If Firestore is unavailable or credentials are not configured, the script automatically falls back to direct MCP calls without caching.

## Cache Management

### When to Refresh Cache

Refresh the cache when:
- RAG metadata has been updated in the Vertex AI corpus
- You suspect stale data in the cache
- After running batch operations that modify RAG files

### Clearing Cache

To clear the cache for a specific workspace/repository, you can use the Firestore console or run a custom script using the `clear_cache_for_workspace()` function from `firestore_utils.py`.

## Jurisdiction Codes Cache

Because `rag_metadata_cache` holds per-document metadata, a second derived cache aggregates all distinct `jurisdiction_code` values used across the collection into a single Firestore document for fast lookup.

### Firestore Path

```
regulations (database)
  └── rag_metadata_summary (collection)
        └── jurisdiction_codes (document)
              ├── codes: ["US", "US-AL", "US-CA", ...]   # sorted list of distinct codes
              ├── count: 52                               # number of distinct codes
              └── updated_at: <UTC timestamp>
```

### When to Run

Run this after `rag-metadata-report` has populated (or updated) the `rag_metadata_cache` collection.

### Command

```bash
cd orca
uv run rag-metadata-build-jurisdiction-cache
```

The script streams all documents from `rag_metadata_cache`, collects every distinct `jurisdiction_code` value, and writes the sorted list to `rag_metadata_summary/jurisdiction_codes`.
