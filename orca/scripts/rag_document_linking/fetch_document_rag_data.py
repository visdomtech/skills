#!/usr/bin/env python3
"""Fetch document and RAG file data via MCP SDK and generate matching report.

Fetches corpus list, RAG files, workspace/repository IDs, and documents, then
runs generate_document_rag_file_report.py to produce the HTML and CSV outputs.

Usage:
    python3 fetch_document_rag_data.py --config <mcp_config.json>
                                       [--corpus-display-name <name>]
                                       [--output <report.html>]
"""

import argparse
import asyncio
import json
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ASSETS_DIR = Path("assets")
RAG_FILES_FILE = ASSETS_DIR / "rag_files.json"
DOCUMENTS_FILE = ASSETS_DIR / "documents.json"
DEFAULT_OUTPUT = ASSETS_DIR / "document_rag_file_report.html"
DEFAULT_CORPUS_DISPLAY_NAME = "prod-s30-w1-r6-happy-quartz"
GENERATE_SCRIPT = Path("scripts/rag_document_linking/generate_document_rag_file_report.py")


def _parse_content(result):
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
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    client = httpx.AsyncClient(headers=config.get("headers", {}), timeout=httpx.Timeout(120.0, connect=30.0))
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


async def fetch_all(config, corpus_display_name):
    async with get_mcp_session(config) as session:
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

        return rag_files, documents, rag_content, doc_content


async def async_main():
    parser = argparse.ArgumentParser(description="Fetch document/RAG data and generate matching report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--corpus-display-name", default=DEFAULT_CORPUS_DISPLAY_NAME,
                        help=f"Corpus display name (default: {DEFAULT_CORPUS_DISPLAY_NAME})")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file path")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    rag_files, documents, rag_content, doc_content = await fetch_all(config, args.corpus_display_name)

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


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    asyncio.run(main())
