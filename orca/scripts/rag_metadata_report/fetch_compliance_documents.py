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
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ASSETS_DIR = Path("assets")
COMPLIANCE_DOCUMENTS_FILE = ASSETS_DIR / "compliance_documents.json"
WORKSPACE_ID = 1
REPOSITORY_ID = 6


def _parse_content(result):
    """Parse MCP tool result content into a dictionary."""
    if not result.content:
        return {}
    if isinstance(result.content, list):
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    return json.loads(item.text)
                except json.JSONDecodeError:
                    continue
            elif isinstance(item, dict):
                return item
    if isinstance(result.content, dict):
        return result.content
    if hasattr(result.content, "text"):
        try:
            return json.loads(result.content.text)
        except json.JSONDecodeError:
            return {}
    return {}


@asynccontextmanager
async def get_mcp_session(config):
    """Yield an initialized MCP session via HTTP/SSE."""
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    client = httpx.AsyncClient(headers=config.get("headers", {}))
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


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


async def main():
    parser = argparse.ArgumentParser(description="Fetch compliance documents for RAG metadata report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    doc_content = await fetch_documents(config)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    COMPLIANCE_DOCUMENTS_FILE.write_text(json.dumps(doc_content, indent=2))
    print(f"\nSaved compliance documents to {COMPLIANCE_DOCUMENTS_FILE}")
    print("Done.")


def async_main():
    """Entry point for console script (uv handles asyncio)."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
