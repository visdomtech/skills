#!/usr/bin/env python3
"""Upsert a single RAG metadata entry: check → create/update → verify → sync Firestore cache.

Usage:
    uv run rag-metadata-upsert \
        --config assets/mcp_config.json \
        --rag-file projects/.../ragFiles/... \
        --key jurisdiction_code \
        --value US

    # Skip Firestore cache sync
    uv run rag-metadata-upsert \
        --config assets/mcp_config.json \
        --rag-file projects/.../ragFiles/... \
        --key jurisdiction_code \
        --value US \
        --no-cache-sync
"""

import argparse
import asyncio
import json
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config


def _detect_value_type(raw: str) -> tuple[str, object]:
    """Detect the value type from a raw string and return (field_name, parsed_value)."""
    # Boolean
    if raw.lower() in ("true", "false"):
        return "valueBool", raw.lower() == "true"
    # Integer
    try:
        return "valueInt", int(raw)
    except ValueError:
        pass
    # Float
    try:
        return "valueFloat", float(raw)
    except ValueError:
        pass
    # Default: string
    return "valueStr", raw


async def list_metadata(session, rag_file: str) -> dict:
    """Call list_rag_metadata and return parsed content."""
    result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file})
    return _parse_content(result)


async def create_metadata(session, rag_file: str, key: str, value_field: str, value) -> dict:
    """Call create_rag_metadata and return parsed content."""
    entry = {"key": key, value_field: value}
    result = await session.call_tool("create_rag_metadata", {
        "ragFileName": rag_file,
        "entries": [entry],
    })
    return _parse_content(result)


async def update_metadata(session, metadata_name: str, key: str, value_field: str, value) -> dict:
    """Call update_rag_metadata and return parsed content."""
    params = {"name": metadata_name, "key": key, value_field: value}
    result = await session.call_tool("update_rag_metadata", params)
    return _parse_content(result)


async def sync_firestore_cache(rag_file_name: str, filename: str, key: str, new_value: str):
    """Update the rag_metadata_cache in Firestore for the given filename."""
    try:
        from scripts.common.firestore_utils import (
            get_firestore_client,
            get_rag_metadata,
            save_rag_metadata,
        )
    except ImportError:
        print("Warning: Firestore utils not available, skipping cache sync.")
        return

    client = get_firestore_client()
    try:
        cached = await get_rag_metadata(client, filename)
        metadata = cached["metadata"] if cached else []

        updated = False
        for entry in metadata:
            if entry.get("key") == key:
                old = entry.get("value")
                entry["value"] = str(new_value)
                updated = True
                print(f"  Cache: {key} {old} -> {new_value}")
                break

        if not updated:
            metadata.append({"key": key, "value": str(new_value)})
            print(f"  Cache: added {key}={new_value}")

        await save_rag_metadata(
            client=client,
            rag_file_name=rag_file_name,
            filename=filename,
            metadata=metadata,
        )
        print(f"  Firestore cache synced for '{filename}'")
    finally:
        pass  # AsyncClient does not need explicit close


async def async_main():
    parser = argparse.ArgumentParser(description="Upsert a single RAG metadata entry")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--rag-file", required=True, help="Full RAG file resource name")
    parser.add_argument("--key", required=True, help="Metadata key (e.g. jurisdiction_code)")
    parser.add_argument("--value", required=True, help="Metadata value (string, int, float, or bool)")
    parser.add_argument("--no-cache-sync", action="store_true",
                        help="Skip Firestore cache sync after upsert")
    parser.add_argument("--filename", default=None,
                        help="Document filename for Firestore cache key. "
                             "If omitted, attempts to look it up from assets/rag_files.json")
    args = parser.parse_args()

    config = load_mcp_config(args.config)
    print(f"Config loaded (URL: {config.get('url')})")

    rag_file = args.rag_file
    key = args.key
    value_field, parsed_value = _detect_value_type(args.value)

    print(f"Target: {rag_file}")
    print(f"Key:    {key}")
    print(f"Value:  {parsed_value} ({value_field})")
    print()

    async with get_mcp_session(config) as session:
        # Step 1: Check existing state
        print("Step 1: Checking existing metadata...")
        content = await list_metadata(session, rag_file)
        metadata_list = content.get("metadata", [])

        existing = None
        existing_name = None
        for m in metadata_list:
            if m.get("key") == key:
                existing = m.get("value")
                existing_name = m.get("name")
                break

        if existing is not None:
            print(f"  Found existing: {key}={existing}")
            if str(existing) == str(parsed_value):
                print(f"  Value already matches. Nothing to do.")
                return
        else:
            print(f"  No existing entry for key '{key}'")

        # Step 2: Create or update
        if existing is None:
            print(f"\nStep 2: Creating metadata entry...")
            result = await create_metadata(session, rag_file, key, value_field, parsed_value)
        else:
            print(f"\nStep 2: Updating metadata entry ({existing} -> {parsed_value})...")
            result = await update_metadata(session, existing_name, key, value_field, parsed_value)

        # Step 3: Verify
        print(f"\nStep 3: Verifying...")
        content = await list_metadata(session, rag_file)
        metadata_list = content.get("metadata", [])

        verified_value = None
        for m in metadata_list:
            if m.get("key") == key:
                verified_value = m.get("value")
                break

        if verified_value is not None and str(verified_value) == str(parsed_value):
            print(f"  VERIFIED: {key}={verified_value}")
        else:
            print(f"  FAILED: expected {parsed_value}, got {verified_value}")
            raise SystemExit(1)

        # Step 4: Sync Firestore cache
        if not args.no_cache_sync:
            print(f"\nStep 4: Syncing Firestore cache...")
            filename = args.filename
            if not filename:
                filename = _lookup_filename_from_cache(rag_file)
            if filename:
                await sync_firestore_cache(rag_file, filename, key, parsed_value)
            else:
                print("  Skipped: could not determine filename for cache sync.")
                print("  Use --filename to specify it explicitly.")
        else:
            print(f"\nStep 4: Firestore cache sync skipped (--no-cache-sync)")

    print("\nDone.")


def _lookup_filename_from_cache(rag_file: str) -> str | None:
    """Try to find the document filename from assets/rag_files.json by RAG file name."""
    rag_files_path = Path("assets/rag_files.json")
    if not rag_files_path.exists():
        return None

    try:
        data = json.loads(rag_files_path.read_text())
        files = data.get("files", data.get("ragFiles", []))
        for f in files:
            if f.get("name") == rag_file:
                return f.get("displayName")
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
