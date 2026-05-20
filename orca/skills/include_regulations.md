# Include Regulations

## Overview

Bulk-import documents for non-included regulations into the Vertex AI RAG corpus. This skill finds all regulations where `included == false`, matches them to repository documents by filename, imports the missing documents via `import_rag_files`, links them back with `set_rag_file_name`, and updates their processing status to `INDEXED`.

**Use this skill when:**
- You need to make all regulations searchable in the RAG corpus
- Downstream skills (like `create_rag_jurisdiction_metadata`) are only seeing a subset of regulations
- New regulations have been added but their documents have not been imported

**Prerequisites:**
- Orca MCP server access
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- MCP config JSON (see Step 1)
- Workspace and repository with a linked RAG corpus

---

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

Save as `assets/mcp_config.json`. **Never commit API keys.**

---

## Step 2: Dry Run (Recommended First)

Always start with a dry run to see what would be imported before making any mutations:

```bash
cd orca
uv sync

uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --dry-run
```

The dry run:
1. Fetches all non-included regulations (`list_regulations` with `included: false`)
2. Fetches all documents in the matching repository (`list_documents`)
3. Matches regulations to documents by filename
4. Checks GCS existence for all candidate URIs (`check_gcs_existence`)
5. Generates `assets/include_regulations_report.csv` with analysis results
6. Prints a console summary

**Review the CSV before proceeding.** It contains columns:
- `regulation_id`, `regulation_short_title`, `jurisdiction_code`
- `filename`, `document_id`, `gs_uri`
- `already_imported`, `gcs_exists`, `error`

---

## Step 3: Run Full Import

After reviewing the dry-run output, run the actual import:

```bash
uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz
```

The script performs the following workflow:

1. **Resolve corpus** — Finds the corpus by display name and locates the matching workspace/repository
2. **Fetch data** — Loads non-included regulations and repository documents
3. **Match** — Links regulations to documents via the `filenames` array
4. **GCS check** — Verifies all candidate GCS URIs exist before importing
5. **Import** — Calls `import_rag_files` and polls `get_import_rag_files_result` until complete
6. **Link** — Calls `set_rag_file_name` in batches of 200 to link documents to RAG files
7. **Status update** — Calls `update_document_status` with `"INDEXED"` in batches of 200
8. **Report** — Generates `assets/include_regulations_report.csv` and console summary

**Auto-detection behavior:** The script resolves `workspace_id` and `repository_id` automatically from the corpus display name. You can override with explicit flags:

```bash
uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --workspace-id 1 \
  --repository-id 6
```

---

## Step 4: Resume After Interruption

If the script is interrupted (Ctrl+C, network timeout, etc.), simply re-run the same command. It will:
- Skip GCS checks for URIs already imported
- Skip `set_rag_file_name` for document IDs already updated
- Skip `update_document_status` for document IDs already indexed

```bash
uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz
```

Progress is tracked in `assets/include_regulations_progress.json`.

To start completely fresh (ignore prior progress):

```bash
uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --reset-progress
```

---

## Step 5: Verify Results

After the import completes, verify the results:

```bash
uv run fetch-document-rag-data --config assets/mcp_config.json
```

Open `assets/document_rag_file_report.html` and confirm that previously non-included regulations now appear as matched.

Alternatively, re-run the dry-run mode and confirm the "already_imported" count has increased:

```bash
uv run include-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --dry-run
```

---

## Report Interpretation

The generated CSV (`assets/include_regulations_report.csv`) contains the following status columns:

| Column | Meaning |
|--------|---------|
| `already_imported` | `yes` if the document already had `rag_file_name` set before this run |
| `gcs_exists` | `yes`/`no` result from `check_gcs_existence` |
| `imported` | `yes` if the document was successfully imported into the RAG corpus |
| `rag_file_name` | The RAG file resource name assigned after import |
| `status_updated` | `yes` if the document status was set to `INDEXED` |
| `error` | Description of any failure for this candidate |

Common error values:
- `Missing document in repository` — The regulation's filename has no matching document
- `GCS URI does not exist` — The document's GCS URI was verified as missing
- `GCS URI reported as non-existent by import` — Import tool could not access the URI
- `Import polling timed out` — The async import operation did not complete within 30 minutes
- `RAG file not found after import` — The imported file did not appear in `list_rag_files`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Corpus not found | Verify the `--corpus-display-name` matches an entry from `list_corpus` |
| No repository linked to corpus | Ensure the workspace has a repository with `corpus_name` set correctly |
| All GCS URIs missing | Verify the documents were uploaded to GCS and the `gsUri` values are correct |
| Import polling times out | Re-run the command to resume; the import may still complete server-side |
| `set_rag_file_name` INTERNAL error | These are often false negatives; the script logs a warning and continues. Verify via `fetch-document-rag-data`. |
| Resume does not skip completed work | Ensure the progress file `assets/include_regulations_progress.json` exists and is valid |

---

## Key Takeaways

1. **Always dry-run first** to understand the scope before mutating data
2. **Resume is safe** — re-running the same command picks up where it left off
3. **GCS existence is checked automatically** before every import (no flag needed)
4. **Batch sizes are tuned** — 100 for import, 200 for updates, matching existing script patterns
5. **Report everything** — the CSV is the source of truth for what happened to each candidate
