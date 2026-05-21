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
from pathlib import Path

from scripts.common.rag_metadata import _parse_content, get_mcp_session, upsert_rag_metadata

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
    """Return list of {filename, key, value} dicts from the CSV.

    Supports two formats:
      - Standard: filename, key, value
      - Report CSV: filename, ..., metadata_key, metadata_value
    """
    path = Path(csv_path)
    if not path.exists():
        print(f"Error: CSV file not found: {csv_path}")
        raise SystemExit(1)
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        # Detect report CSV format (from rag_metadata_report.csv)
        if "metadata_key" in fieldnames and "metadata_value" in fieldnames:
            return [
                {"filename": r["filename"].strip(), "key": r["metadata_key"].strip(), "value": r["metadata_value"].strip()}
                for r in reader
            ]
        # Standard format
        required = {"filename", "key", "value"}
        if not required.issubset(fieldnames):
            missing = required - fieldnames
            print(f"Error: CSV missing required columns: {missing}")
            raise SystemExit(1)
        return [{"filename": r["filename"].strip(), "key": r["key"].strip(), "value": r["value"].strip()} for r in reader]


async def fetch_valid_keys(session):
    """Call list_rag_data_schemas and return the set of valid key names.

    Returns None if the tool is unavailable or the response is unrecognised,
    so the caller can decide whether to abort or skip validation.
    """
    try:
        result = await session.call_tool("list_rag_data_schemas", {})
        content = _parse_content(result)
        schemas = None
        if isinstance(content, list):
            schemas = content
        elif isinstance(content, dict):
            schemas = content.get("schemas") or content.get("data") or content.get("items")
        if schemas and isinstance(schemas, list):
            keys = set()
            for s in schemas:
                k = s.get("key") or s.get("name")
                if k:
                    keys.add(k)
            return keys if keys else None
        return None
    except Exception as e:
        print(f"Warning: could not call list_rag_data_schemas: {e}", flush=True)
        return None


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

    # Validate filenames before opening MCP session; skip rows without a matching document
    # or without a rag_file_name (can't set metadata on un-imported docs)
    errors = []
    skipped_rows = []
    valid_rows = []
    for i, row in enumerate(rows, start=2):  # row 1 is header
        if row["filename"] not in doc_map:
            errors.append(f"  Row {i}: filename not found in compliance_documents.json: {row['filename']!r}")
            skipped_rows.append(row)
        else:
            valid_rows.append(row)
    if errors:
        print(f"Warning: Skipped {len(skipped_rows)} rows (document not found or not imported):")
        for e in errors:
            print(e)
    rows = valid_rows
    if not rows:
        print("No valid rows to process. Exiting.")
        raise SystemExit(0)

    async with get_mcp_session(config) as session:
        # Schema key validation
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
            async with semaphore:
                status, detail = await upsert_rag_metadata(session, rag, row["key"], row["value"])
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
