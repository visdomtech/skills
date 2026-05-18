"""Shared utilities for RAG metadata upsert operations."""

import json
from contextlib import asynccontextmanager

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def get_mcp_session(config):
    """Yield an initialized MCP session via HTTP/SSE."""
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    client = httpx.AsyncClient(headers=config.get("headers", {}), timeout=60.0)
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


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


async def get_current_value(session, rag_file_name, key):
    """Return the current metadata value for key on the RAG file, or None if absent."""
    result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file_name})
    content = _parse_content(result)
    for entry in (content.get("metadata") or []):
        if entry.get("key") == key:
            return entry.get("value")
    return None


async def upsert_rag_metadata(session, rag_file_name, key, value, firestore_client=None):
    """Create or update a single RAG metadata key-value pair.

    Returns (status, detail) where status is one of:
        "created"  — metadata key was absent and has been written
        "updated"  — metadata key existed with a different value and has been updated
        "skipped"  — metadata key already had the expected value; no write performed
        "failed"   — write failed and could not be verified

    When firestore_client is provided, a Firestore cache fast-path is attempted
    before hitting the MCP API, and results are cached after MCP reads.
    """
    # Firestore cache fast-path (skip MCP read if cache confirms current value)
    if firestore_client:
        from scripts.rag_metadata_report.firestore_utils import get_rag_metadata, save_rag_metadata
        filename = rag_file_name.split("/")[-1] if "/" in rag_file_name else rag_file_name
        try:
            cached = await get_rag_metadata(firestore_client, filename)
            if cached:
                for entry in (cached.get("metadata") or []):
                    if entry.get("key") == key and entry.get("value") == value:
                        return "skipped", "cache confirmed"
        except Exception as e:
            print(f"    Warning: Firestore cache read failed for {filename}: {e}", flush=True)

    # Read current value from MCP
    try:
        result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file_name})
        content = _parse_content(result)
        entries = content.get("metadata") or []
        current = None
        for entry in entries:
            if entry.get("key") == key:
                current = entry.get("value")
                break

        # Cache MCP read result in Firestore
        if firestore_client:
            try:
                filename = rag_file_name.split("/")[-1] if "/" in rag_file_name else rag_file_name
                from scripts.rag_metadata_report.firestore_utils import save_rag_metadata
                await save_rag_metadata(
                    client=firestore_client,
                    rag_file_name=rag_file_name,
                    filename=filename,
                    metadata=entries,
                )
            except Exception as e:
                print(f"    Warning: Firestore cache write failed: {e}", flush=True)

    except Exception as e:
        return "failed", f"list_rag_metadata failed: {e}"

    if current == value:
        return "skipped", None

    # Write
    try:
        tool = "create_rag_metadata" if current is None else "update_rag_metadata"
        write_result = await session.call_tool(
            tool, {"ragFileName": rag_file_name, "entries": [{"key": key, "valueStr": value}]}
        )

        if write_result.isError:
            err_text = str(write_result.content)
            if "INTERNAL" in err_text:
                # Re-verify — MCP often returns INTERNAL on success
                verified = await get_current_value(session, rag_file_name, key)
                if verified == value:
                    action = "created" if current is None else "updated"
                    return action, "false-negative INTERNAL"
            return "failed", err_text

        # Post-update verification for updates (creates are implicitly verified above)
        if current is not None:
            verified = await get_current_value(session, rag_file_name, key)
            if verified != value:
                return "failed", f"verification mismatch: expected {value!r}, got {verified!r}"

        action = "created" if current is None else "updated"
        return action, None

    except Exception as e:
        return "failed", str(e)
