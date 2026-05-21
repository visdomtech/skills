#!/usr/bin/env python3
"""Fetch compliance repository documents for RAG metadata report.

Fetches all documents from workspace 1, repository 6 (compliance) and saves them
to assets/compliance_documents.json for use by generate_rag_metadata_report.py.

Usage:
    python3 fetch_compliance_documents.py --config <mcp_config.json>
"""

import argparse
import asyncio
import json
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config


ASSETS_DIR = Path("assets")
COMPLIANCE_DOCUMENTS_FILE = ASSETS_DIR / "compliance_documents.json"
WORKSPACE_ID = 1
REPOSITORY_ID = 6


async def fetch_documents(config):
    """Fetch all documents from the compliance repository."""
    async with get_mcp_session(config) as session:
        print(f"Fetching documents from workspace {WORKSPACE_ID}, repository {REPOSITORY_ID}...")
        result = await session.call_tool("list_documents", {
            "workspaceId": WORKSPACE_ID,
            "repositoryId": REPOSITORY_ID,
            "limit": 2**31 - 1,
        })
        doc_content = _parse_content(result)
        documents = doc_content.get("documents", [])
        print(f"Fetched {len(documents)} documents")
        return doc_content


async def async_main():
    parser = argparse.ArgumentParser(description="Fetch compliance documents for RAG metadata report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    args = parser.parse_args()

    config = load_mcp_config(args.config)
    print(f"Config loaded (URL: {config.get('url')})")

    doc_content = await fetch_documents(config)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    COMPLIANCE_DOCUMENTS_FILE.write_text(json.dumps(doc_content, indent=2))
    print(f"\nSaved compliance documents to {COMPLIANCE_DOCUMENTS_FILE}")
    print("Done.")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    asyncio.run(main())
