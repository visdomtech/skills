# Include Regulations

## Overview

Bulk-import documents for regulations into the Vertex AI RAG corpus. This skill follows a clear 3-step workflow:

1. **Generate enriched CSV** — Fetches all regulations, matches them to documents, and writes an enriched CSV for review
2. **Review & confirm** — Review the CSV summary showing which documents need import (empty `rag_file_name`), then confirm before proceeding
3. **Process import** — Imports all documents with missing/empty `rag_file_name` into RAG, links them with `set_rag_file_name`, and updates status to `INDEXED`

The script uses the document's **`rag_file_name`** as the source of truth for whether import is needed. Missing document records are **auto-created** via `create_document` when needed.

**Use this skill when:**
- You need to make all regulations searchable in the RAG corpus
- Downstream skills (like `rag-metadata-create-jurisdiction`) are only seeing a subset of regulations
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

## Pipeline

This skill uses the `rag-import-regulations` script, which internally relies on `scripts/common/tools/mcp_wrapper_base.py` for all MCP communication.

### Step 1: Prepare Environment

```bash
cd orca
uv sync
```

### Step 2: Dry Run with Limited Scope

Always start with a dry run on a small subset to verify the pipeline before processing all rows. Generate the enriched CSV and review it:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --dry-run
```

Review both CSVs:
- **`assets/include_regulations_to_import.csv`** — start here; it shows only the rows that will be imported (empty `rag_file_name`)
- `assets/include_regulations_enriched.csv` — full dataset for deep inspection if needed

If the data looks correct, proceed. If not, fix any issues and retry.

### Step 3: Full Import (with Confirmation)

After reviewing the enriched CSV, run the actual import:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz
```

### Step 4: Verify Output

Review `assets/include_regulations_report.csv` to confirm all imports succeeded.

---

## Step 2: Generate Enriched CSV (Dry Run)

Always start with a dry run to generate the enriched CSV for review before importing:

```bash
cd orca
uv sync

uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --dry-run
```

The dry run:
1. Fetches all regulations (`list_regulations`)
2. Fetches all documents in the matching repository (`list_documents`)
3. Matches regulations to documents by filename
4. Checks GCS existence for all candidate URIs (`check_gcs_existence`)
5. Generates two CSVs for review:
   - `assets/include_regulations_enriched.csv` — full regulation + document data (all rows)
   - `assets/include_regulations_to_import.csv` — **focused view with only the rows that need importing**
6. Prints a **Pre-Import Summary** showing how many need import

> **Note:** Dry-run does **not** create missing documents or import anything. The full import (Step 3) will automatically call `create_document` for any missing files before proceeding.

**Review the focused CSV first.** `include_regulations_to_import.csv` contains only the rows that need importing:

| Column | Meaning |
|--------|---------|
| `regulation_id` | Regulation ID |
| `short_title` | Short title of the regulation |
| `jurisdiction_code` | Jurisdiction code (e.g., `US-FL`) |
| `filename` | Document filename |
| `document_id` | Document ID in the repository |
| `gs_uri` | GCS URI of the document |
| `gcs_exists` | `yes` if the GCS URI was verified to exist |
| `error` | Any error message (e.g., missing document, missing GCS) |

The enriched CSV (`include_regulations_enriched.csv`) contains all rows with these columns:
- `regulation_id`, `short_title`, `official_title`, `jurisdiction_code`
- `category`, `status`, `created_at`, `effective_date`, `statute_code`
- `filenames`, `document_id`, `upload_date`, `gs_uri`, `document_status`
- `rag_file_name` (empty = needs import), `document_workspace_id`, `document_repository_id`

Use `--report-path` to customize the output location:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --dry-run \
  --report-path reports/2026-05-19_batch.csv
```

---

## Step 3: Run Full Import (with Confirmation)

After reviewing the enriched CSV, run the actual import:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz
```

The script performs the following workflow:

1. **Resolve corpus** — Finds the corpus by display name and locates the matching workspace/repository
2. **Fetch data** — Loads all regulations and repository documents
3. **Match** — Links regulations to documents via the `filenames` array
4. **Generate enriched CSV** — Writes `assets/include_regulations_enriched.csv` for review
5. **Pre-import summary** — Shows how many documents already have `rag_file_name` vs. need import
6. **Confirmation prompt** — Asks "Proceed with importing? [y/N]" before mutating data
7. **Create missing** — For any regulation whose filename has no matching document, calls `create_document` to add the missing record, then re-fetches and re-matches
8. **GCS check** — Verifies all candidate GCS URIs exist before importing
9. **Import** — Calls `import_rag_files` and polls `get_import_rag_files_result` until complete
10. **Link** — Calls `set_rag_file_name` in batches of 200 to link documents to RAG files
11. **Status update** — Calls `update_document_status` with `"INDEXED"` in batches of 200
12. **Report** — Generates `assets/include_regulations_report.csv` with operation results

**Skip confirmation** with `--yes` (useful for CI/CD or non-interactive environments):

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --yes
```

**Auto-detection behavior:** The script resolves `workspace_id` and `repository_id` automatically from the corpus display name. You can override with explicit flags:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --workspace-id 1 \
  --repository-id 6
```

---

## Step 3a: Batch Import by Date

Instead of importing all regulations at once, you can filter by regulation creation date. This is useful when a new batch of regulations has just been added (e.g., a set of AI regulations created on 2026-05-19).

**Step 1 — Generate enriched CSV for the date batch:**

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --since-date 2026-05-19 \
  --dry-run \
  --report-path reports/2026-05-19_batch.csv
```

Review `reports/2026-05-19_batch.csv` and confirm the rows with empty `rag_file_name` are the ones you want to import.

**Step 2 — Run the actual date-batched import:**

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --since-date 2026-05-19
```

You can also combine `--since-date` and `--until-date` to target a specific window:

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --since-date 2026-05-01 \
  --until-date 2026-05-31 \
  --dry-run
```

---

## Step 3b: Batch Import from ID List

To import only specific regulations, create a file containing one regulation ID per line (or a CSV where the first column is the regulation ID) and pass it with `--regulation-ids-file`.

**Example ID list file (`assets/target_regulation_ids.txt`):**

```
2489
2486
2502
```

**Step 1 — Generate enriched CSV for the ID list:**

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --regulation-ids-file assets/target_regulation_ids.txt \
  --dry-run \
  --report-path reports/target_batch.csv
```

Review `reports/target_batch.csv` and confirm the rows with empty `rag_file_name` are the ones you want to import.

**Step 2 — Run the actual ID-list import:**

```bash
uv run rag-import-regulations \
  --config assets/mcp_config.json \
  --corpus-display-name prod-s30-w1-r6-happy-quartz \
  --regulation-ids-file assets/target_regulation_ids.txt
```

---



## Step 5: Verify Results

After the import completes, verify the results:

```bash
uv run rag-document-fetch-data --config assets/mcp_config.json
```

Open `assets/document_rag_file_report.html` and confirm that previously non-included regulations now appear as matched.

Alternatively, re-run the dry-run mode and confirm the "already_imported" count has increased:

```bash
uv run rag-import-regulations \
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
- `Failed to create document for '{filename}'` — `create_document` returned an error for a missing file
- `Exception creating document for '{filename}'` — An unexpected error occurred during `create_document`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Corpus not found | Verify the `--corpus-display-name` matches an entry from `list_corpus` |
| No repository linked to corpus | Ensure the workspace has a repository with `corpus_name` set correctly |
| All GCS URIs missing | Verify the documents were uploaded to GCS and the `gsUri` values are correct |
| Import polling times out | Re-run the command to resume; the import may still complete server-side |
| `set_rag_file_name` INTERNAL error | These are often false negatives; the script logs a warning and continues. Verify via `rag-document-fetch-data`. |
| Resume does not skip completed work | Ensure the progress file `assets/include_regulations_progress.json` exists and is valid |

---

## Key Takeaways

1. **3-step workflow** — Generate CSVs → Review focused CSV → Confirm → Process import
2. **Always dry-run first** to generate the enriched CSV and understand the scope before mutating data
3. **rag_file_name is the gate** — Documents with existing `rag_file_name` are skipped; only empty ones are imported
4. **Confirmation prompt** — The script asks before importing unless you pass `--yes`
5. **Progress is always reset** — each run starts fresh with a clean state
6. **GCS existence is checked automatically** before every import (no flag needed)
7. **Batch sizes are tuned** — 100 for import, 200 for updates, matching existing script patterns
8. **Three CSVs are generated** — The focused CSV (only rows needing import), the enriched CSV (all rows for deep review), and the operation report CSV (for post-import results)
9. **Batch filtering is available** — use `--since-date`, `--until-date`, or `--regulation-ids-file` to target specific regulation batches instead of processing everything at once
