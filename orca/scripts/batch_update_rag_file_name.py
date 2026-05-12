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

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


WORKSPACE_ID = 1
BATCH_SIZE = 200


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


async def get_mcp_session(config):
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    async with streamablehttp_client(url=config["url"], headers=config.get("headers", {})) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


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


async def process_batches(session, entries):
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
                "workspaceId": WORKSPACE_ID,
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


async def main():
    parser = argparse.ArgumentParser(description="Batch-update rag_file_name via MCP SDK")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--csv", required=True, help="Path to CSV file from generate_document_rag_file_report.py")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    entries = load_csv(csv_path)
    if not entries:
        print("No entries found in CSV.")
        raise SystemExit(1)
    print(f"Loaded {len(entries)} entries from {csv_path}")

    async for session in get_mcp_session(config):
        success, failed = await process_batches(session, entries)

    print(f"\n{'='*60}")
    print(f"COMPLETE: {success}/{len(entries)} updated successfully")
    if failed:
        print(f"Failed ({len(failed)}):")
        for e in failed:
            print(f"  documentId={e['documentId']} ragFileName={e['ragFileName']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
