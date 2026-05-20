#!/usr/bin/env python3
"""Include regulations by importing their documents into the RAG corpus.

Finds all regulations where included == false, matches them to repository
documents by filename, imports missing documents via import_rag_files, links
them back with set_rag_file_name, and updates their status to INDEXED.

Usage:
    uv run include-regulations --config assets/mcp_config.json
    uv run include-regulations --config assets/mcp_config.json --dry-run
"""

import argparse
import asyncio
import csv
import json
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.common.rag_metadata import _parse_content, get_mcp_session

# --- Configuration ---
DEFAULT_CORPUS_DISPLAY_NAME = "prod-s30-w1-r6-happy-quartz"
PROGRESS_FILE = Path("assets/include_regulations_progress.json")
REPORT_CSV = Path("assets/include_regulations_report.csv")
BATCH_SIZE_IMPORT = 100
BATCH_SIZE_UPDATE = 200
BATCH_SIZE_GCS_CHECK = 100
POLL_INTERVAL = 10  # seconds
MAX_POLL_TIME = 30 * 60  # 30 minutes


# --- Data model ---
@dataclass
class Candidate:
    regulation_id: int
    regulation_short_title: str
    jurisdiction_code: str
    filename: str
    document_id: int
    gs_uri: str
    already_imported: bool = False
    gcs_exists: bool | None = None
    imported: bool = False
    rag_file_name: str | None = None
    status_updated: bool = False
    error: str = ""


# --- Progress tracking ---
def load_progress() -> dict[str, Any]:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            print("Warning: Progress file corrupted, starting fresh")
    return _default_progress()


def _default_progress() -> dict[str, Any]:
    return {
        "version": 1,
        "corpus_display_name": None,
        "workspace_id": None,
        "repository_id": None,
        "corpus_name": None,
        "step": "analysis",
        "imported_uris": [],
        "update_rag_completed_ids": [],
        "update_status_completed_ids": [],
        "report_generated": False,
    }


def save_progress(state: dict[str, Any]) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = PROGRESS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2))
    temp.rename(PROGRESS_FILE)


def reset_progress() -> None:
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()


# --- MCP helpers ---

async def resolve_corpus_and_workspace(session, corpus_display_name: str) -> tuple[str, int, int]:
    """Resolve corpus resource name, workspace_id, and repository_id.

    Finds the corpus by display name, then scans workspaces/repositories
    to find the one linked to that corpus.
    """
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

    # Extract corpus ID for matching
    corpus_id = corpus_name.split("/")[-1] if "/" in corpus_name else corpus_name
    print(f"Looking for repository with corpus ID: {corpus_id}")

    result = await session.call_tool("list_workspaces", {})
    ws_content = _parse_content(result)
    workspaces = ws_content.get("workspaces", [])

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
            repo_corpus_id = repo_corpus.split("/")[-1] if "/" in repo_corpus else repo_corpus
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

    return corpus_name, workspace_id, repository_id


async def fetch_non_included_regulations(session, workspace_id: int) -> list[dict]:
    """Fetch all regulations where included == false."""
    print(f"Fetching non-included regulations for workspace {workspace_id}...")
    result = await session.call_tool(
        "list_regulations",
        {"workspaceId": workspace_id, "limit": 2**31 - 1, "included": False}
    )
    content = _parse_content(result)
    regs = content.get("regulations") or []
    non_included = [r for r in regs if not r.get("included", True)]
    print(f"Found {len(non_included)} non-included regulations out of {len(regs)} total")
    return non_included


async def fetch_documents(session, workspace_id: int, repository_id: int) -> list[dict]:
    """Fetch all documents in the repository."""
    print(f"Fetching documents (workspace={workspace_id}, repo={repository_id})...")
    result = await session.call_tool(
        "list_documents",
        {"workspaceId": workspace_id, "repositoryId": repository_id, "limit": 2**31 - 1}
    )
    content = _parse_content(result)
    docs = content.get("documents") or []
    print(f"Fetched {len(docs)} documents")
    return docs


def match_regulations_to_documents(regulations: list[dict], documents: list[dict]) -> list[Candidate]:
    """Match regulations to documents by filename.

    Returns a list of Candidate objects, one per unique document that needs importing.
    """
    # Build document map: filename -> document
    doc_map: dict[str, dict] = {}
    for doc in documents:
        fname = doc.get("filename")
        if fname:
            doc_map[fname] = doc

    candidates: list[Candidate] = []
    seen_doc_ids: set[int] = set()

    for reg in regulations:
        reg_id = reg.get("id") or reg.get("regulation_id")
        short_title = reg.get("short_title") or reg.get("shortTitle") or ""
        jurisdiction = reg.get("jurisdiction", {})
        jurisdiction_code = jurisdiction.get("code") if isinstance(jurisdiction, dict) else ""
        filenames = reg.get("filenames", [])

        for fname in filenames:
            doc = doc_map.get(fname)
            if not doc:
                # Regulation references a filename with no matching document
                candidates.append(Candidate(
                    regulation_id=reg_id,
                    regulation_short_title=short_title,
                    jurisdiction_code=jurisdiction_code,
                    filename=fname,
                    document_id=-1,
                    gs_uri="",
                    already_imported=False,
                    error="Missing document in repository",
                ))
                continue

            doc_id = doc.get("id") or doc.get("document_id")
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)

            rag_name = doc.get("rag_file_name") or doc.get("ragFileName")
            gs_uri = doc.get("gs_uri") or doc.get("gsUri") or ""

            candidates.append(Candidate(
                regulation_id=reg_id,
                regulation_short_title=short_title,
                jurisdiction_code=jurisdiction_code,
                filename=fname,
                document_id=doc_id,
                gs_uri=gs_uri,
                already_imported=bool(rag_name),
                rag_file_name=rag_name,
            ))

    print(f"Matched {len(candidates)} unique document candidates")
    already = sum(1 for c in candidates if c.already_imported)
    missing = sum(1 for c in candidates if c.document_id == -1)
    print(f"  Already imported: {already}, Missing documents: {missing}")
    return candidates


async def create_missing_documents(session, workspace_id: int, repository_id: int, candidates: list[Candidate]) -> tuple[int, list[str]]:
    """Create document records for missing files and return count + errors."""
    missing = [c for c in candidates if c.document_id == -1]
    if not missing:
        return 0, []

    # Deduplicate by filename
    unique_missing: dict[str, Candidate] = {}
    for c in missing:
        if c.filename not in unique_missing:
            unique_missing[c.filename] = c

    print(f"Creating {len(unique_missing)} missing document records...")
    created = 0
    errors: list[str] = []

    for c in unique_missing.values():
        gs_uri = f"regulations/{workspace_id}/{c.filename}"
        try:
            result = await session.call_tool(
                "create_document",
                {
                    "workspaceId": workspace_id,
                    "repositoryId": repository_id,
                    "filename": c.filename,
                    "documentType": "PDF",
                    "uploadedBy": 2,
                    "gsUri": gs_uri,
                },
            )
            if result.isError:
                err_text = str(result.content)
                errors.append(f"Failed to create document for '{c.filename}': {err_text}")
                print(f"  Error creating '{c.filename}': {err_text}")
            else:
                content = _parse_content(result)
                doc_id = content.get("documentId") or content.get("document_id")
                if doc_id:
                    created += 1
                    print(f"  Created document {doc_id} for '{c.filename}'")
                else:
                    errors.append(f"Created document but no ID returned for '{c.filename}'")
        except Exception as e:
            errors.append(f"Exception creating document for '{c.filename}': {e}")
            print(f"  Exception creating '{c.filename}': {e}")

    print(f"Document creation complete: {created}/{len(unique_missing)} created")
    return created, errors


async def check_gcs_existence(session, candidates: list[Candidate]) -> list[Candidate]:
    """Check which candidate GCS URIs exist. Always runs per spec."""
    # Filter to candidates that need checking
    to_check = [c for c in candidates if c.gs_uri and not c.already_imported and c.document_id != -1]
    if not to_check:
        print("No GCS URIs to check")
        return candidates

    print(f"Checking GCS existence for {len(to_check)} URIs...")

    for i in range(0, len(to_check), BATCH_SIZE_GCS_CHECK):
        batch = to_check[i : i + BATCH_SIZE_GCS_CHECK]
        uris = [c.gs_uri for c in batch]
        print(f"  Batch {i // BATCH_SIZE_GCS_CHECK + 1}: {len(batch)} URIs")

        try:
            result = await session.call_tool("check_gcs_existence", {"gcsUris": uris})
            content = _parse_content(result)
            existing = set(content.get("existing") or content.get("exist") or [])
            missing = set(content.get("missing") or content.get("nonExist") or [])

            for c in batch:
                if c.gs_uri in existing:
                    c.gcs_exists = True
                elif c.gs_uri in missing:
                    c.gcs_exists = False
                    c.error = "GCS URI does not exist"
                else:
                    # Ambiguous result — assume exists to let import handle it
                    c.gcs_exists = True
        except Exception as e:
            print(f"  Warning: GCS check failed for batch: {e}")
            # Assume all exist to let import handle errors
            for c in batch:
                c.gcs_exists = True

    exists_count = sum(1 for c in candidates if c.gcs_exists is True)
    missing_count = sum(1 for c in candidates if c.gcs_exists is False)
    print(f"GCS check complete: {exists_count} exist, {missing_count} missing")
    return candidates


async def import_documents(session, corpus_name: str, candidates: list[Candidate]) -> list[Candidate]:
    """Import candidate documents into the RAG corpus."""
    import_candidates = [c for c in candidates if c.gcs_exists and not c.already_imported and c.document_id != -1]
    if not import_candidates:
        print("No documents to import")
        return candidates

    uris = [c.gs_uri for c in import_candidates]
    print(f"Importing {len(uris)} documents into corpus...")

    try:
        result = await session.call_tool("import_rag_files", {"corpusName": corpus_name, "gcsUris": uris})
        content = _parse_content(result)

        # Track non-existent URIs reported by the import tool
        non_exist = content.get("nonExist", content.get("non_exist", []))
        if non_exist:
            non_exist_set = set(non_exist)
            for c in import_candidates:
                if c.gs_uri in non_exist_set:
                    c.error = "GCS URI reported as non-existent by import"
            print(f"  Import skipped {len(non_exist)} non-existent URIs")

        # Poll for completion
        operation_name = content.get("operationName") or content.get("operation_name")
        if operation_name:
            print(f"  Polling import operation: {operation_name}")
            poll_start = time.time()
            while True:
                await asyncio.sleep(POLL_INTERVAL)
                poll_result = await session.call_tool("get_import_rag_files_result", {})
                poll_content = _parse_content(poll_result)
                done = poll_content.get("done", poll_content.get("complete", False))
                if done:
                    print("  Import operation complete")
                    break
                if time.time() - poll_start > MAX_POLL_TIME:
                    print("  Warning: Import polling timed out")
                    for c in import_candidates:
                        if not c.error:
                            c.error = "Import polling timed out"
                    break

        # Mark imported candidates (unless they had errors)
        for c in import_candidates:
            if not c.error:
                c.imported = True

        print(f"  Import finished: {sum(1 for c in import_candidates if c.imported)} imported")

    except Exception as e:
        print(f"  Import failed: {e}")
        for c in import_candidates:
            if not c.error:
                c.error = f"Import failed: {e}"

    return candidates


async def update_rag_file_names(session, workspace_id: int, candidates: list[Candidate], progress: dict) -> list[Candidate]:
    """List RAG files and update rag_file_name on matched documents."""
    # Fetch current RAG files in the corpus
    corpus_name = progress.get("corpus_name", "")
    if not corpus_name:
        print("Error: corpus_name not available for RAG file listing")
        return candidates

    print(f"Fetching RAG files from corpus...")
    result = await session.call_tool("list_rag_files", {"corpusName": corpus_name})
    content = _parse_content(result)
    rag_files = content.get("files", content.get("ragFiles", []))
    print(f"Found {len(rag_files)} RAG files")

    # Build map: displayName -> name
    rag_map: dict[str, str] = {}
    for rf in rag_files:
        display = rf.get("displayName") or rf.get("display_name")
        name = rf.get("name")
        if display and name:
            rag_map[display] = name

    # Prepare entries for set_rag_file_name
    entries: list[dict] = []
    entry_to_candidate: dict[int, Candidate] = {}

    completed_ids: set[int] = set(progress.get("update_rag_completed_ids", []))

    for c in candidates:
        if c.document_id == -1 or c.already_imported or not c.imported:
            continue
        if c.document_id in completed_ids:
            c.rag_file_name = rag_map.get(c.filename, c.rag_file_name)
            continue

        rag_name = rag_map.get(c.filename)
        if rag_name:
            entries.append({"documentId": c.document_id, "ragFileName": rag_name})
            entry_to_candidate[len(entries) - 1] = c
        else:
            c.error = "RAG file not found after import"

    if not entries:
        print("No rag_file_name updates needed")
        return candidates

    print(f"Updating rag_file_name for {len(entries)} documents...")
    total = len(entries)
    success = 0
    num_batches = (total + BATCH_SIZE_UPDATE - 1) // BATCH_SIZE_UPDATE

    for i in range(0, total, BATCH_SIZE_UPDATE):
        batch_num = i // BATCH_SIZE_UPDATE + 1
        batch = entries[i : i + BATCH_SIZE_UPDATE]

        try:
            result = await session.call_tool(
                "set_rag_file_name",
                {"workspaceId": workspace_id, "entries": batch}
            )
            if result.isError:
                err_text = str(result.content)
                print(f"  Batch {batch_num}/{num_batches} error: {err_text}")
                # Handle false-negative INTERNAL errors
                if "INTERNAL" in err_text:
                    print("    Warning: INTERNAL error — may be false negative")
                for idx in range(i, min(i + BATCH_SIZE_UPDATE, total)):
                    c = entry_to_candidate.get(idx)
                    if c and not c.error:
                        c.error = f"set_rag_file_name error: {err_text}"
            else:
                for idx in range(i, min(i + BATCH_SIZE_UPDATE, total)):
                    c = entry_to_candidate.get(idx)
                    if c:
                        c.rag_file_name = batch[idx - i].get("ragFileName")
                        success += 1
                print(f"  Batch {batch_num}/{num_batches} OK ({success}/{total})")

                # Track completed IDs
                for idx in range(i, min(i + BATCH_SIZE_UPDATE, total)):
                    c = entry_to_candidate.get(idx)
                    if c:
                        progress["update_rag_completed_ids"].append(c.document_id)
                save_progress(progress)

        except Exception as e:
            print(f"  Batch {batch_num}/{num_batches} exception: {e}")
            for idx in range(i, min(i + BATCH_SIZE_UPDATE, total)):
                c = entry_to_candidate.get(idx)
                if c and not c.error:
                    c.error = f"set_rag_file_name exception: {e}"

    print(f"rag_file_name update complete: {success}/{total}")
    return candidates


async def update_document_statuses(session, workspace_id: int, candidates: list[Candidate], progress: dict) -> list[Candidate]:
    """Update document status to INDEXED."""
    doc_ids = []
    id_to_candidate: dict[int, Candidate] = {}

    completed_ids: set[int] = set(progress.get("update_status_completed_ids", []))

    for c in candidates:
        if c.document_id == -1 or c.already_imported:
            continue
        if c.document_id in completed_ids:
            c.status_updated = True
            continue
        if c.imported and c.rag_file_name and not c.error:
            doc_ids.append(c.document_id)
            id_to_candidate[c.document_id] = c

    if not doc_ids:
        print("No document status updates needed")
        return candidates

    print(f"Updating document status to INDEXED for {len(doc_ids)} documents...")
    total = len(doc_ids)
    success = 0
    num_batches = (total + BATCH_SIZE_UPDATE - 1) // BATCH_SIZE_UPDATE

    for i in range(0, total, BATCH_SIZE_UPDATE):
        batch_num = i // BATCH_SIZE_UPDATE + 1
        batch = doc_ids[i : i + BATCH_SIZE_UPDATE]

        try:
            result = await session.call_tool(
                "update_document_status",
                {"workspaceId": workspace_id, "documentIds": batch, "status": "INDEXED"}
            )
            if result.isError:
                err_text = str(result.content)
                print(f"  Batch {batch_num}/{num_batches} error: {err_text}")
                for doc_id in batch:
                    c = id_to_candidate.get(doc_id)
                    if c and not c.error:
                        c.error = f"update_document_status error: {err_text}"
            else:
                for doc_id in batch:
                    c = id_to_candidate.get(doc_id)
                    if c:
                        c.status_updated = True
                        success += 1
                print(f"  Batch {batch_num}/{num_batches} OK ({success}/{total})")

                progress["update_status_completed_ids"].extend(batch)
                save_progress(progress)

        except Exception as e:
            print(f"  Batch {batch_num}/{num_batches} exception: {e}")
            for doc_id in batch:
                c = id_to_candidate.get(doc_id)
                if c and not c.error:
                    c.error = f"update_document_status exception: {e}"

    print(f"Status update complete: {success}/{total}")
    return candidates


def generate_csv_report(candidates: list[Candidate], output_path: Path) -> None:
    """Write a CSV report of the operation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "regulation_id", "regulation_short_title", "jurisdiction_code",
            "filename", "document_id", "gs_uri", "already_imported",
            "gcs_exists", "imported", "rag_file_name", "status_updated", "error"
        ])
        for c in candidates:
            writer.writerow([
                c.regulation_id,
                c.regulation_short_title,
                c.jurisdiction_code,
                c.filename,
                c.document_id if c.document_id != -1 else "",
                c.gs_uri,
                "yes" if c.already_imported else "no",
                "yes" if c.gcs_exists else ("no" if c.gcs_exists is False else ""),
                "yes" if c.imported else "no",
                c.rag_file_name or "",
                "yes" if c.status_updated else "no",
                c.error,
            ])

    print(f"Report saved to {output_path}")


def print_summary(candidates: list[Candidate]) -> None:
    """Print a console summary."""
    total = len(candidates)
    already = sum(1 for c in candidates if c.already_imported)
    missing_doc = sum(1 for c in candidates if c.document_id == -1)
    missing_gcs = sum(1 for c in candidates if c.gcs_exists is False)
    imported = sum(1 for c in candidates if c.imported)
    rag_set = sum(1 for c in candidates if c.rag_file_name and not c.already_imported)
    status_set = sum(1 for c in candidates if c.status_updated)
    failed = sum(1 for c in candidates if c.error and not c.already_imported)

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total candidates:          {total}")
    print(f"Already imported:          {already}")
    print(f"Missing documents:         {missing_doc}")
    print(f"Missing GCS URIs:          {missing_gcs}")
    print(f"Imported to RAG:           {imported}")
    print(f"rag_file_name updated:     {rag_set}")
    print(f"Status set to INDEXED:     {status_set}")
    print(f"Failed:                    {failed}")
    print(f"{'='*60}")


# --- Main orchestrator ---

async def async_main():
    parser = argparse.ArgumentParser(description="Include regulations by importing documents into RAG corpus")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--corpus-display-name", default=DEFAULT_CORPUS_DISPLAY_NAME,
                        help=f"Corpus display name (default: {DEFAULT_CORPUS_DISPLAY_NAME})")
    parser.add_argument("--workspace-id", type=int, default=None, help="Workspace ID (optional, auto-detected by default)")
    parser.add_argument("--repository-id", type=int, default=None, help="Repository ID (optional, auto-detected by default)")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only; do not import or mutate")
    parser.add_argument("--reset-progress", action="store_true", help="Clear progress file and start fresh")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    if args.reset_progress:
        reset_progress()
        print("Progress reset")

    progress = load_progress()

    async with get_mcp_session(config) as session:
        # Resolve workspace/repository/corpus
        if args.workspace_id is not None and args.repository_id is not None:
            workspace_id = args.workspace_id
            repository_id = args.repository_id
            # Still need to resolve corpus name from repository
            result = await session.call_tool("list_repositories", {"workspaceId": workspace_id})
            repo_content = _parse_content(result)
            repos = repo_content.get("repositories", [])
            corpus_name = None
            for repo in repos:
                if (repo.get("id") or repo.get("repository_id")) == repository_id:
                    corpus_name = repo.get("corpus_name")
                    break
            if not corpus_name:
                print(f"Error: Repository {repository_id} not found in workspace {workspace_id}")
                raise SystemExit(1)
            print(f"Using explicit workspace={workspace_id}, repository={repository_id}, corpus={corpus_name}")
        else:
            corpus_name, workspace_id, repository_id = await resolve_corpus_and_workspace(
                session, args.corpus_display_name
            )

        # Update progress with resolved IDs
        progress["corpus_display_name"] = args.corpus_display_name
        progress["workspace_id"] = workspace_id
        progress["repository_id"] = repository_id
        progress["corpus_name"] = corpus_name
        save_progress(progress)

        # Fetch data
        regulations = await fetch_non_included_regulations(session, workspace_id)
        documents = await fetch_documents(session, workspace_id, repository_id)
        candidates = match_regulations_to_documents(regulations, documents)

        # Create missing documents (non-dry-run only)
        if not args.dry_run:
            created_count, _ = await create_missing_documents(
                session, workspace_id, repository_id, candidates
            )
            if created_count > 0:
                print(f"\nRe-fetching documents after creating {created_count} new records...")
                documents = await fetch_documents(session, workspace_id, repository_id)
                candidates = match_regulations_to_documents(regulations, documents)

        # Check GCS existence (always, per spec)
        candidates = await check_gcs_existence(session, candidates)
        progress["step"] = "gcs_check"
        save_progress(progress)

        if args.dry_run:
            print("\n*** DRY RUN — no mutations performed ***")
            generate_csv_report(candidates, REPORT_CSV)
            print_summary(candidates)
            return

        # Import to RAG
        if progress["step"] in ("analysis", "gcs_check"):
            # Skip URIs already imported (from prior run)
            imported_uris_set = set(progress.get("imported_uris", []))
            for c in candidates:
                if c.gs_uri in imported_uris_set:
                    c.imported = True
            
            candidates_to_import = [c for c in candidates if c.gs_uri not in imported_uris_set]
            candidates = await import_documents(session, corpus_name, candidates)
            
            # Track newly imported URIs
            for c in candidates:
                if c.imported and c.gs_uri and c.gs_uri not in imported_uris_set:
                    progress["imported_uris"].append(c.gs_uri)
            progress["step"] = "import"
            save_progress(progress)

        # Update rag_file_name
        if progress["step"] in ("gcs_check", "import"):
            candidates = await update_rag_file_names(session, workspace_id, candidates, progress)
            progress["step"] = "update_rag"
            save_progress(progress)

        # Update document status
        if progress["step"] in ("import", "update_rag"):
            candidates = await update_document_statuses(session, workspace_id, candidates, progress)
            progress["step"] = "update_status"
            save_progress(progress)

        # Generate report
        generate_csv_report(candidates, REPORT_CSV)
        print_summary(candidates)
        progress["step"] = "complete"
        progress["report_generated"] = True
        save_progress(progress)

        print("\nDone!")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
