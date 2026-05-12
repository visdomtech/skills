# RAG Jurisdiction Metadata Report

## Overview

This skill describes how to generate a comprehensive report on the jurisdiction metadata associated with documents in the `prod-s30-w1-r6-happy-quartz` compliance repository. The process uses the Python MCP SDK to fetch metadata for each document in parallel and produces two outputs:
1. A detailed CSV file containing all metadata entries for every document.
2. An HTML summary report highlighting jurisdiction distribution and identifying documents missing jurisdiction metadata.

## Prerequisites

- Access to the Orca MCP server.
- Python environment with `mcp` SDK installed (use `uv` as per project standards).
- Workspace ID: 1, Repository ID: 6.
- Documents data cached at `orca/assets/compliance_documents.json`.

## Step 1: Prepare Environment

Before running the script, ensure your virtual environment is set up and dependencies are installed:

```bash
uv venv --allow-existing
uv pip install mcp
source .venv/bin/activate
```

## Step 2: Run the Script

Execute the generation script using your MCP configuration:

```bash
python3 orca/scripts/rag_metadata_report/generate_rag_metadata_report.py --config orca/assets/mcp_config.json
```

The script will:
1. Load the list of documents from `orca/assets/compliance_documents.json`.
2. Connect to the Orca MCP server.
3. Fetch metadata for each document's associated RAG file in parallel (concurrency limit: 3).
4. Generate `orca/assets/rag_metadata_report.csv` with detailed metadata.
5. Generate `orca/assets/rag_metadata_summary.html` with a visual summary.

## Output Files

### 1. Detailed CSV (`rag_metadata_report.csv`)
Contains one row per metadata entry. If a document has multiple metadata keys, it will have multiple rows.

| Column | Description |
| :--- | :--- |
| `filename` | The name of the compliance document. |
| `rag_file_name` | The full resource name of the associated RAG file. |
| `metadata_key` | The key of the metadata entry (e.g., `jurisdiction_code`). |
| `metadata_value` | The value of the metadata entry. |

### 2. Summary HTML (`rag_metadata_summary.html`)
A professional, Gmail-compatible HTML report containing:
- **Summary Metrics**: Total documents, count with jurisdiction metadata, and count without.
- **Jurisdiction Distribution**: A table showing the number of documents grouped by their `jurisdiction_code`.
- **Missing Metadata List**: A list of filenames that do not have a `jurisdiction_code` metadata entry.

## Implementation Details

- **Parallel Processing**: The script uses `asyncio.Semaphore` to limit concurrent API calls, ensuring high performance without overwhelming the MCP server.
- **Error Handling**: If metadata fetching fails for a specific document, the error is logged and recorded in the CSV, but processing continues for other documents.
- **Progress Tracking**: The script prints progress updates to the console (e.g., "Processed 50/1300 documents...").
