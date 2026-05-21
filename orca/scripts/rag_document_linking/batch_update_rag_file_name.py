#!/usr/bin/env python3
"""Batch-update rag_file_name for documents via MCP SDK.

Reads the CSV produced by generate_document_rag_file_report.py and calls
set_rag_file_name in batches of 200 entries.

Usage:
    python3 batch_update_rag_file_name.py --config <mcp_config.json> --csv <report.csv>
"""

import argparse
import asyncio
import csv
import json
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config


BATCH_SIZE = 200
DEFAULT_WORKSPACE_ID = None  # Will be auto-detected or use default


def load_csv(csv_path):
    entries = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc_id = row.get("document_id") or row.get("Document ID") or row.get("id")
            rag_name = row.get("correct_rag_file_name") or row.get("Correct RAG File Name") or row.get("rag_file_name")
            if doc_id and rag_name:
                entries.append({"documentId": int(doc_id), "ragFileName": rag_name})
    return entries


async def process_batches(session, entries, workspace_id):
    total = len(entries)
    success = 0
    failed = []
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for i in range(0, total, BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch = entries[i : i + BATCH_SIZE]
        print(f"Processing batch {batch_num}/{num_batches} ({len(batch)} entries)...")

        try:
            result = await session.call_tool("set_rag_file_name", {
                "workspaceId": workspace_id,
                "entries": batch,
            })
            if result.isError:
                print(f"  Batch {batch_num} error: {result.content}")
                failed.extend(batch)
            else:
                success += len(batch)
                print(f"  Batch {batch_num} OK ({success}/{total} total)")
        except Exception as e:
            print(f"  Batch {batch_num} exception: {e}")
            failed.extend(batch)

    return success, failed


async def _async_main():
    parser = argparse.ArgumentParser(description="Batch-update rag_file_name via MCP SDK")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--csv", required=True, help="Path to CSV file from generate_document_rag_file_report.py")
    parser.add_argument("--workspace-id", type=int, default=DEFAULT_WORKSPACE_ID, 
                        help="Workspace ID (optional, will prompt if not provided)")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}")
        raise SystemExit(1)

    config = load_mcp_config(args.config)
    print(f"Config loaded (URL: {config.get('url')})")

    entries = load_csv(csv_path)
    if not entries:
        print("No entries found in CSV.")
        raise SystemExit(1)
    print(f"Loaded {len(entries)} entries from {csv_path}")

    # Determine workspace ID
    workspace_id = args.workspace_id
    if workspace_id is None:
        print("\nNote: --workspace-id not specified.")
        print("You can specify it with: --workspace-id <id>")
        print("Using default workspace ID: 1")
        workspace_id = 1
    else:
        print(f"Using workspace ID: {workspace_id}")

    async with get_mcp_session(config) as session:
        success, failed = await process_batches(session, entries, workspace_id)

    print(f"\n{'='*60}")
    print(f"COMPLETE: {success}/{len(entries)} updated successfully")
    if failed:
        print(f"Failed ({len(failed)}):")
        for e in failed:
            print(f"  documentId={e['documentId']} ragFileName={e['ragFileName']}")
    print(f"{'='*60}")


def main():
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
