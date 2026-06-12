#!/usr/bin/env python3
"""Import a single document into RAG corpus."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

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
)


async def import_single_document(config_path: str, corpus_display_name: str, document_id: int, filename: str, gs_uri: str, workspace_id: int):
    config = load_mcp_config(config_path)
    
    async with get_mcp_session(config) as session:
        # Resolve corpus
        result = await session.call_tool("list_corpus", {})
        content = _parse_content(result)
        corpora = content.get("corpora", content.get("ragCorpora", []))
        corpus_name = None
        for c in corpora:
            if c.get("displayName") == corpus_display_name:
                corpus_name = c.get("name")
                break
        if not corpus_name:
            print(f"Corpus '{corpus_display_name}' not found.")
            raise SystemExit(1)
        
        print(f"Corpus: {corpus_name}")
        
        # Create candidate
        candidate = Candidate(
            regulation_id=-1,
            regulation_short_title="",
            jurisdiction_code="",
            filename=filename,
            document_id=document_id,
            gs_uri=gs_uri,
            already_imported=False,
        )
        
        # Check GCS
        candidates = await check_gcs_existence(session, [candidate])
        if not candidates[0].gcs_exists:
            print(f"GCS URI not found: {gs_uri}")
            print(f"Error: {candidates[0].error}")
            raise SystemExit(1)
        
        print(f"GCS exists: {gs_uri}")
        
        # Import to RAG
        candidates = await import_documents(session, corpus_name, candidates)
        
        # Update rag_file_name
        progress = _default_progress()
        progress["corpus_display_name"] = corpus_display_name
        progress["workspace_id"] = workspace_id
        progress["repository_id"] = 6
        progress["corpus_name"] = corpus_name
        
        candidates = await update_rag_file_names(session, workspace_id, candidates, progress)
        candidates = await update_document_statuses(session, workspace_id, candidates, progress)
        
        # Report
        c = candidates[0]
        print(f"\nImport result:")
        print(f"  Filename: {c.filename}")
        print(f"  Document ID: {c.document_id}")
        print(f"  GCS URI: {c.gs_uri}")
        print(f"  Imported: {'YES' if c.imported else 'NO'}")
        print(f"  RAG File Name: {c.rag_file_name}")
        print(f"  Status Updated: {'YES' if c.status_updated else 'NO'}")
        print(f"  Error: {c.error or 'None'}")


def main():
    parser = argparse.ArgumentParser(description="Import a single document into RAG")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--document-id", type=int, required=True, help="Document ID")
    parser.add_argument("--filename", required=True, help="Document filename")
    parser.add_argument("--gs-uri", required=True, help="GCS URI of the document")
    parser.add_argument("--workspace-id", type=int, default=1, help="Workspace ID")
    parser.add_argument("--corpus-display-name", default="prod-s30-w1-r6-happy-quartz", help="Corpus display name")
    args = parser.parse_args()
    
    asyncio.run(import_single_document(
        args.config, args.corpus_display_name, args.document_id, args.filename, args.gs_uri, args.workspace_id
    ))


if __name__ == "__main__":
    main()
