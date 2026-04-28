# Orca

The `orca/` directory contains skill files designed to work with the **Orca MCP server** — a collection of tools for managing jurisdictions, regulations, documents, and RAG-based document search.

## MCP Tools

### Jurisdictions & Regulations

- `list_jurisdictions` — List all jurisdictions
- `upsert_jurisdiction` — Insert or update a jurisdiction (partial update on conflict)
- `list_regulations` — List regulations with filters (workspace, jurisdiction, category, status, pagination)
- `get_latest_law_changes` — Get law changes from Firestore since a given date
- `send_law_change_notifications` — Send law change email notifications via Mailgun

### Workspaces & Repositories

- `list_workspaces` — List all workspaces
- `list_repositories` — List repositories for a workspace
- `list_documents` — List documents in a repository (ordered by upload date desc)
- `create_document` — Create a new document record in a repository

### Document Processing & RAG

- `import_rag_files` — Start async GCS-to-Vertex-AI-RAG-corpus import (skips non-existent URIs)
- `get_import_rag_files_result` — Poll the status of a running RAG import
- `list_corpus` — List all RAG corpora
- `list_rag_files` — List RAG files within a corpus
- `set_rag_file_name` — Set the Vertex AI RAG file name and record processed timestamp
- `update_document_status` — Update document processing status (with optional error message)

### GCS (Google Cloud Storage)

- `list_gcs_files` — List objects under a GCS bucket path
- `check_gcs_existence` — Check which GCS URIs exist

### Email

- `send_email` — Send an email via Mailgun (text or HTML, with CC/BCC)

## Summary

Orca manages **jurisdictions** and **regulations**, organizes them into **workspaces/repositories** with **documents**, imports documents into **Vertex AI RAG** for search, tracks **law changes**, and sends **email notifications** — all backed by GCS.
