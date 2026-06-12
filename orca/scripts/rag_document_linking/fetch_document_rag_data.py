#!/usr/bin/env python3
"""Fetch document and RAG file data via MCP SDK and generate matching report.

Fetches corpus list, RAG files, workspace/repository IDs, and documents, then
runs generate_document_rag_file_report.py to produce the HTML and CSV outputs.

Optionally imports unmatched documents (those with no corresponding RAG file)
into the RAG corpus via --import-unmatched.

Usage:
    python3 fetch_document_rag_data.py --config <mcp_config.json>
                                       [--corpus-display-name <name>]
                                       [--output <report.html>]
                                       [--import-unmatched]
                                       [--yes]
"""

import argparse
import asyncio
import csv
import json
import subprocess
import sys
from pathlib import Path

import httpx
from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config
from scripts.rag_import_regulations.include_regulations import (
    Candidate,
    check_gcs_existence,
    import_documents,
    update_rag_file_names,
    update_document_statuses,
    save_progress,
    _default_progress,
    generate_csv_report,
)


ASSETS_DIR = Path("assets")
RAG_FILES_FILE = ASSETS_DIR / "rag_files.json"
DOCUMENTS_FILE = ASSETS_DIR / "documents.json"
DEFAULT_OUTPUT = ASSETS_DIR / "document_rag_file_report.html"
DEFAULT_CORPUS_DISPLAY_NAME = "prod-s30-w1-r6-happy-quartz"
GENERATE_SCRIPT = Path("scripts/rag_document_linking/generate_document_rag_file_report.py")
UNMATCHED_CSV = ASSETS_DIR / "document_rag_file_report_unmatched.csv"
UNMATCHED_REPORT_CSV = ASSETS_DIR / "document_rag_file_report_unmatched_report.csv"


def find_unmatched_documents(documents: list[dict], rag_files: list[dict]) -> list[dict]:
    """Identify documents with no matching RAG file in the corpus.

    Returns list of documents where filename has no corresponding RAG displayName.
    """
    rag_display_names = set()
    for rf in rag_files:
        display_name = rf.get("displayName", "")
        if display_name:
            rag_display_names.add(display_name)

    unmatched = []
    for doc in documents:
        filename = doc.get("filename", "")
        if not filename:
            continue
        if filename not in rag_display_names:
            unmatched.append(doc)

    return unmatched


def build_candidates_from_documents(documents: list[dict], workspace_id: int) -> list[Candidate]:
    """Build Candidate objects from unmatched documents for import."""
    candidates = []
    for doc in documents:
        doc_id = doc.get("id") or doc.get("document_id")
        filename = doc.get("filename", "")
        gs_uri = doc.get("gs_uri") or doc.get("gsUri") or f"regulations/{workspace_id}/{filename}"

        candidates.append(Candidate(
            regulation_id=-1,  # Not regulation-linked
            regulation_short_title="",
            jurisdiction_code="",
            filename=filename,
            document_id=doc_id,
            gs_uri=gs_uri,
            already_imported=False,
        ))

    return candidates


def generate_unmatched_csv(candidates: list[Candidate], output_path: Path) -> None:
    """Write a CSV containing unmatched documents pending import."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "document_id", "filename", "gs_uri", "gcs_exists", "error",
        ])
        for c in candidates:
            writer.writerow([
                c.document_id if c.document_id != -1 else "",
                c.filename,
                c.gs_uri,
                "yes" if c.gcs_exists else "no",
                c.error,
            ])

    print(f"Unmatched documents CSV saved to {output_path} ({len(candidates)} rows)")


async def fetch_all(config, corpus_display_name):
    async with get_mcp_session(config, timeout=httpx.Timeout(120.0, connect=30.0)) as session:
        # Step 1: Resolve corpus resource name
        print(f"Fetching corpus list to find '{corpus_display_name}'...")
        result = await session.call_tool("list_corpus", {})
        content = _parse_content(result)
        corpora = content.get("corpora", content.get("ragCorpora", []))
        corpus_name = None
        for c in corpora:
            if c.get("displayName") == corpus_display_name:
                corpus_name = c.get("name")
                break
        if not corpus_name:
            print(f"Error: Corpus '{corpus_display_name}' not found. Available:")
            for c in corpora:
                print(f"  - {c.get('displayName')} ({c.get('name')})")
            raise SystemExit(1)
        print(f"Resolved corpus: {corpus_name}")

        # Step 2: Fetch RAG files
        print("Fetching RAG files...")
        result = await session.call_tool("list_rag_files", {"corpusName": corpus_name})
        rag_content = _parse_content(result)
        rag_files = rag_content.get("files", rag_content.get("ragFiles", []))
        if not rag_files:
            print(f"Error: list_rag_files returned 0 files for corpus '{corpus_name}'.")
            print("This is likely a transient API issue. Please re-run the command.")
            raise SystemExit(1)
        print(f"Fetched {len(rag_files)} RAG files")

        # Step 3: Find workspace and repository matching the corpus
        print("Fetching workspaces...")
        result = await session.call_tool("list_workspaces", {})
        ws_content = _parse_content(result)
        workspaces = ws_content.get("workspaces", [])

        # Extract corpus ID for matching (last segment of the resource name)
        corpus_id = corpus_name.split('/')[-1] if '/' in corpus_name else corpus_name
        print(f"Looking for repository with corpus ID: {corpus_id}")

        workspace_id = None
        repository_id = None
        for ws in workspaces:
            ws_id = ws.get("id") or ws.get("workspace_id")
            print(f"  Checking workspace {ws_id}...")
            result = await session.call_tool("list_repositories", {"workspaceId": ws_id})
            repo_content = _parse_content(result)
            repos = repo_content.get("repositories", [])
            for repo in repos:
                repo_corpus = repo.get("corpus_name", "")
                # Match by corpus ID (last segment) to handle different project ID formats
                repo_corpus_id = repo_corpus.split('/')[-1] if '/' in repo_corpus else repo_corpus
                if repo_corpus_id == corpus_id:
                    workspace_id = ws_id
                    repository_id = repo.get("id") or repo.get("repository_id")
                    print(f"Found: workspaceId={workspace_id}, repositoryId={repository_id}")
                    break
            if workspace_id:
                break

        if not workspace_id:
            print(f"Error: No repository found with corpus_name='{corpus_name}'")
            raise SystemExit(1)

        # Step 4: Fetch documents
        print(f"Fetching documents (workspace={workspace_id}, repo={repository_id})...")
        result = await session.call_tool("list_documents", {
            "workspaceId": workspace_id,
            "repositoryId": repository_id,
            "limit": 2**31 - 1,
        })
        doc_content = _parse_content(result)
        documents = doc_content.get("documents", [])
        print(f"Fetched {len(documents)} documents")

        return rag_files, documents, rag_content, doc_content, corpus_name, workspace_id, repository_id


async def async_main():
    parser = argparse.ArgumentParser(description="Fetch document/RAG data and generate matching report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--corpus-display-name", default=DEFAULT_CORPUS_DISPLAY_NAME,
                        help=f"Corpus display name (default: {DEFAULT_CORPUS_DISPLAY_NAME})")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file path")
    parser.add_argument("--import-unmatched", action="store_true",
                        help="Import unmatched documents into the RAG corpus after report generation")
    parser.add_argument("--yes", action="store_true",
                        help="Skip the interactive confirmation prompt for unmatched import (used by agents after getting user approval)")
    args = parser.parse_args()

    config = load_mcp_config(args.config)
    print(f"Config loaded (URL: {config.get('url')})")

    rag_files, documents, rag_content, doc_content, corpus_name, workspace_id, repository_id = await fetch_all(config, args.corpus_display_name)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    RAG_FILES_FILE.write_text(json.dumps(rag_content, indent=2))
    DOCUMENTS_FILE.write_text(json.dumps(doc_content, indent=2))
    print(f"\nSaved RAG files to {RAG_FILES_FILE}")
    print(f"Saved documents to {DOCUMENTS_FILE}")

    print(f"\nGenerating report...")
    result = subprocess.run(
        [sys.executable, str(GENERATE_SCRIPT), str(DOCUMENTS_FILE), str(RAG_FILES_FILE), str(Path(args.output))],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"Report generation failed (exit code {result.returncode})")
        raise SystemExit(result.returncode)

    print(f"\nDone. Report saved to {args.output}")

    # --- Unmatched document import flow ---
    unmatched_docs = find_unmatched_documents(documents, rag_files)

    if not unmatched_docs:
        print("\nNo unmatched documents found. All documents have corresponding RAG files.")
        return

    print(f"\n{'='*60}")
    print(f"UNMATCHED DOCUMENTS: {len(unmatched_docs)}")
    print(f"{'='*60}")
    for doc in unmatched_docs:
        doc_id = doc.get("id") or doc.get("document_id")
        filename = doc.get("filename", "")
        print(f"  document_id={doc_id}  filename={filename}")
    print(f"{'='*60}")

    if not args.import_unmatched:
        print("\nTo import these unmatched documents into the RAG corpus, re-run with:")
        print(f"  uv run rag-document-fetch-data --config {args.config} --import-unmatched")
        return

    # Build candidates from unmatched documents
    candidates = build_candidates_from_documents(unmatched_docs, workspace_id)
    generate_unmatched_csv(candidates, UNMATCHED_CSV)

    if not args.yes:
        try:
            response = input(f"\nImport {len(candidates)} unmatched document(s) into RAG? [y/N]: ").strip().lower()
        except (EOFError, OSError):
            print("Non-interactive mode detected. Use --yes to skip confirmation.")
            raise SystemExit(1)
        if response not in ("y", "yes"):
            print("Aborted by user.")
            return

    print("\nProceeding with unmatched document import...")

    progress = _default_progress()
    progress["corpus_display_name"] = args.corpus_display_name
    progress["workspace_id"] = workspace_id
    progress["repository_id"] = repository_id
    progress["corpus_name"] = corpus_name
    save_progress(progress)

    async with get_mcp_session(config) as session:
        # Check GCS existence
        candidates = await check_gcs_existence(session, candidates)

        # Report non-importable candidates
        non_importable = [c for c in candidates if not c.gcs_exists]
        if non_importable:
            print(f"\n{len(non_importable)} document(s) skipped (GCS URI not found):")
            for c in non_importable:
                print(f"  {c.filename}: {c.error}")

        importable = [c for c in candidates if c.gcs_exists]
        if not importable:
            print("\nNo unmatched documents have valid GCS URIs. Nothing to import.")
            generate_csv_report(candidates, UNMATCHED_REPORT_CSV)
            return

        # Import to RAG
        candidates = await import_documents(session, corpus_name, candidates)

        # Update rag_file_name
        candidates = await update_rag_file_names(session, workspace_id, candidates, progress)

        # Update document status to INDEXED
        candidates = await update_document_statuses(session, workspace_id, candidates, progress)

        # Generate operation report
        generate_csv_report(candidates, UNMATCHED_REPORT_CSV)

    imported_count = sum(1 for c in candidates if c.imported)
    failed_count = sum(1 for c in candidates if c.error)
    print(f"\n{'='*60}")
    print(f"UNMATCHED IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"Total unmatched:    {len(candidates)}")
    print(f"Imported to RAG:    {imported_count}")
    print(f"Failed:             {failed_count}")
    print(f"Report:             {UNMATCHED_REPORT_CSV}")
    print(f"{'='*60}")

    print(f"\nRe-run the report to verify all documents are now matched:")
    print(f"  uv run rag-document-fetch-data --config {args.config}")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    asyncio.run(main())
