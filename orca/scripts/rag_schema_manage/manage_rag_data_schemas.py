#!/usr/bin/env python3
"""Manage RAG data schemas: list, add, or delete schema keys.

Usage:
    rag-schema-manage --config <path> --corpus-name <name> --action list
    rag-schema-manage --config <path> --corpus-name <name> --action add --key <key> [--data-type STRING]
    rag-schema-manage --config <path> --corpus-name <name> --action delete --key <key> --confirm

Actions:
    list    Print all current schema keys and their data types.
    add     Add a new schema key. Aborts if the key already exists.
    delete  Delete a schema key. Requires --confirm flag. Never deletes jurisdiction_code.
"""

import argparse
import asyncio
import json
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config

VALID_DATA_TYPES = {"INTEGER", "FLOAT", "STRING", "DATETIME", "BOOLEAN"}
PROTECTED_KEYS = {"jurisdiction_code"}


def _parse_schemas(content):
    """Extract list of schema dicts from list_rag_data_schemas response."""
    if isinstance(content, list):
        return content
    if isinstance(content, dict):
        for k in ("schemas", "data", "items"):
            val = content.get(k)
            if isinstance(val, list):
                return val
    return []


def _extract_corpus_name(content):
    """Best-effort extraction of corpusName from list_rag_data_schemas response."""
    if isinstance(content, dict):
        for k in ("corpusName", "corpus_name", "parent"):
            val = content.get(k)
            if val:
                return val
    return None


def _print_schema_table(schemas, corpus_name=None):
    if corpus_name:
        print(f"CorpusName: {corpus_name}")
    print(f"\nCurrent RAG Data Schemas ({len(schemas)} total):")
    if not schemas:
        print("  (none)")
        return
    max_key = max((len(s.get("key", "")) for s in schemas), default=0)
    for i, s in enumerate(schemas, start=1):
        key = s.get("key", "")
        dtype = s.get("dataType") or s.get("data_type") or s.get("type", "")
        print(f"  {i:>3}. {key:<{max_key}}  {dtype}")


async def do_list(session, corpus_name):
    result = await session.call_tool("list_rag_data_schemas", {"corpusName": corpus_name})
    content = _parse_content(result)
    schemas = _parse_schemas(content)
    _print_schema_table(schemas, corpus_name)
    return schemas


async def do_add(session, corpus_name, key, data_type):
    print(f"Fetching current schemas...", flush=True)
    schemas = await do_list(session, corpus_name)

    existing_keys = {s.get("key") for s in schemas}
    if key in existing_keys:
        print(f"\nError: key '{key}' already exists in the schema. No changes made.")
        raise SystemExit(1)

    print(f"\nAdding schema key '{key}' (dataType={data_type})...", flush=True)
    write_result = await session.call_tool(
        "create_rag_data_schema",
        {"corpusName": corpus_name, "key": key, "dataType": data_type},
    )
    if write_result.isError:
        print(f"Error: create_rag_data_schema failed: {write_result.content}")
        raise SystemExit(1)

    print("Done. Verifying...", flush=True)
    await do_list(session, corpus_name)


async def do_delete(session, corpus_name, key):
    if key in PROTECTED_KEYS:
        print(f"Error: '{key}' is a protected key and cannot be deleted.")
        raise SystemExit(1)

    print(f"Fetching current schemas...", flush=True)
    schemas = await do_list(session, corpus_name)

    existing_keys = {s.get("key") for s in schemas}
    if key not in existing_keys:
        print(f"\nError: key '{key}' not found in schema. No changes made.")
        raise SystemExit(1)

    schema_name = next((s.get("name") for s in schemas if s.get("key") == key), None)
    if not schema_name:
        print(f"\nError: could not find resource name for key '{key}'. No changes made.")
        raise SystemExit(1)

    print(f"\nDeleting schema key '{key}'...", flush=True)
    write_result = await session.call_tool(
        "delete_rag_data_schema",
        {"name": schema_name},
    )
    if write_result.isError:
        print(f"Error: delete_rag_data_schema failed: {write_result.content}")
        raise SystemExit(1)

    print("Done. Verifying...", flush=True)
    await do_list(session, corpus_name)


async def async_main():
    parser = argparse.ArgumentParser(description="Manage RAG data schemas")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--corpus-name", required=True, dest="corpus_name",
                        help="Full corpus resource name (e.g. projects/.../ragCorpora/...)")
    parser.add_argument("--action", required=True, choices=["list", "add", "delete"],
                        help="Action to perform")
    parser.add_argument("--key", help="Schema key name (required for add and delete)")
    parser.add_argument("--data-type", default="STRING", dest="data_type",
                        help=f"Data type for add action. One of: {', '.join(sorted(VALID_DATA_TYPES))}. Default: STRING")
    parser.add_argument("--confirm", action="store_true",
                        help="Required for delete action to confirm irreversible deletion")
    args = parser.parse_args()

    config = load_mcp_config(args.config)

    if args.action in ("add", "delete") and not args.key:
        print(f"Error: --key is required for --action {args.action}")
        raise SystemExit(1)

    if args.action == "add":
        data_type = args.data_type.upper()
        if data_type not in VALID_DATA_TYPES:
            print(f"Error: invalid --data-type '{args.data_type}'. Must be one of: {', '.join(sorted(VALID_DATA_TYPES))}")
            raise SystemExit(1)

    if args.action == "delete" and not args.confirm:
        print(f"Pass --confirm to proceed with deletion of '{args.key}'.")
        raise SystemExit(1)

    async with get_mcp_session(config) as session:
        if args.action == "list":
            await do_list(session, args.corpus_name)
        elif args.action == "add":
            await do_add(session, args.corpus_name, args.key, data_type)
        elif args.action == "delete":
            await do_delete(session, args.corpus_name, args.key)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
