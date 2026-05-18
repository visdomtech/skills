#!/usr/bin/env python3
"""Create or update RAG metadata for documents specified in a CSV file.

CSV format (one metadata operation per row):
    filename,key,value

- filename: must match a document filename in assets/compliance_documents.json
- key:      must be a valid schema key from list_rag_data_schemas
- value:    the string value to write

Upsert logic per row:
- key absent  → create_rag_metadata
- key matches → skip (idempotent)
- key differs → update_rag_metadata

INTERNAL MCP errors are re-verified via list_rag_metadata; treated as success
if the metadata appears after the error.
"""

import argparse
import asyncio
import csv
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DOCUMENTS_FILE = Path("assets/compliance_documents.json")
CONCURRENCY_LIMIT = 3


def load_documents():
    """Return a {filename: rag_file_name} mapping from the cached JSON."""
    if not DOCUMENTS_FILE.exists():
        print(f"Error: {DOCUMENTS_FILE} not found. Run fetch-compliance-documents first.")
        raise SystemExit(1)
    with open(DOCUMENTS_FILE) as f:
        data = json.load(f)
    if "response" in data and "data" in data["response"]:
        docs = data["response"]["data"].get("documents", [])
    else:
        docs = data.get("documents", [])
    return {d["filename"]: d["rag_file_name"] for d in docs if d.get("rag_file_name")}


def load_csv(csv_path):
    """Return list of {filename, key, value} dicts from the CSV."""
    path = Path(csv_path)
    if not path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        raise SystemExit(1)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        required = {"filename", "key", "value"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            print(f"Error: CSV missing required columns: {missing}")
            raise SystemExit(1)
        return [{"filename": r["filename"].strip(), "key": r["key"].strip(), "value": r["value"].strip()} for r in reader]


@asynccontextmanager
async def get_mcp_session(config):
    client = httpx.AsyncClient(headers=config.get("headers", {}), timeout=60.0)
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


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


async def fetch_valid_keys(session):
    """Call list_rag_data_schemas and return the set of valid key names.

    Returns None if the tool is unavailable or the response is unrecognised,
    so the caller can decide whether to abort or skip validation.
    """
    try:
        result = await session.call_tool("list_rag_data_schemas", {})
        content = _parse_content(result)
        # Try common response shapes: list at top-level, or under "schemas"/"data"
        schemas = None
        if isinstance(content, list):
            schemas = content
        elif isinstance(content, dict):
            schemas = content.get("schemas") or content.get("data") or content.get("items")
        if schemas and isinstance(schemas, list):
            keys = set()
            for s in schemas:
                # Accept either {"key": "..."} or {"name": "..."}
                k = s.get("key") or s.get("name")
                if k:
                    keys.add(k)
            return keys if keys else None
        return None
    except Exception as e:
        print(f"Warning: could not call list_rag_data_schemas: {e}", flush=True)
        return None


async def get_current_value(session, rag_file_name, key):
    """Return the current value for key on the RAG file, or None if absent."""
    result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file_name})
    content = _parse_content(result)
    for entry in content.get("metadata") or []:
        if entry.get("key") == key:
            return entry.get("value")
    return None


async def check_and_upsert(session, semaphore, rag_file_name, key, value):
    """Upsert one metadata key-value pair. Returns (status, detail)."""
    async with semaphore:
        try:
            current = await get_current_value(session, rag_file_name, key)

            if current == value:
                return "skipped", None

            tool = "create_rag_metadata" if current is None else "update_rag_metadata"
            entries = [{"key": key, "valueStr": value}]
            result = await session.call_tool(tool, {"ragFileName": rag_file_name, "entries": entries})

            if result.isError:
                err_text = str(result.content)
                if "INTERNAL" in err_text:
                    # Re-verify — MCP often returns INTERNAL on success
                    verified = await get_current_value(session, rag_file_name, key)
                    if verified == value:
                        action = "created" if current is None else "updated"
                        return action, "false-negative INTERNAL"
                return "failed", err_text

            action = "created" if current is None else "updated"
            return action, None

        except Exception as e:
            return "failed", str(e)


async def async_main():
    parser = argparse.ArgumentParser(description="Create/update RAG metadata from a CSV file")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--csv", required=True, dest="csv_path", help="Path to input CSV (filename,key,value)")
    parser.add_argument("--skip-schema-validation", action="store_true",
                        help="Skip key validation against list_rag_data_schemas")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: config not found: {config_path}")
        raise SystemExit(1)
    config = json.loads(config_path.read_text())

    doc_map = load_documents()
    rows = load_csv(args.csv_path)

    # --- Validate CSV ---
    errors = []
    for i, row in enumerate(rows, start=2):  # row 1 is header
        if row["filename"] not in doc_map:
            errors.append(f"  Row {i}: filename not found in compliance_documents.json: {row['filename']!r}")
    if errors:
        print("Validation errors (filename not found):")
        for e in errors:
            print(e)
        raise SystemExit(1)

    async with get_mcp_session(config) as session:
        # --- Schema validation ---
        if not args.skip_schema_validation:
            print("Fetching available RAG data schemas...", flush=True)
            valid_keys = await fetch_valid_keys(session)
            if valid_keys is None:
                print("Warning: list_rag_data_schemas returned no keys or is unavailable.")
                print("         Use --skip-schema-validation to bypass. Aborting.")
                raise SystemExit(1)
            print(f"Valid schema keys: {sorted(valid_keys)}", flush=True)
            bad_keys = [row for row in rows if row["key"] not in valid_keys]
            if bad_keys:
                print("Validation errors (invalid keys):")
                for row in bad_keys:
                    print(f"  filename={row['filename']!r} key={row['key']!r}")
                raise SystemExit(1)

        total = len(rows)
        print(f"Processing {total} rows...", flush=True)

        semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
        counts = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}
        failures = []

        async def process_row(i, row):
            rag = doc_map[row["filename"]]
            status, detail = await check_and_upsert(session, semaphore, rag, row["key"], row["value"])
            counts[status] += 1
            if status == "failed":
                failures.append({"filename": row["filename"], "key": row["key"], "detail": detail})
            if (i + 1) % 10 == 0 or (i + 1) == total:
                print(f"Processed {i + 1}/{total} rows...", flush=True)

        await asyncio.gather(*[process_row(i, row) for i, row in enumerate(rows)])

    print("\n--- Summary ---")
    print(f"  Created: {counts['created']}")
    print(f"  Updated: {counts['updated']}")
    print(f"  Skipped: {counts['skipped']} (value already matched)")
    print(f"  Failed:  {counts['failed']}")
    if failures:
        print("\nFailed rows:")
        for f in failures:
            print(f"  {f['filename']} [{f['key']}]: {f['detail']}")
    print("Done.", flush=True)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
