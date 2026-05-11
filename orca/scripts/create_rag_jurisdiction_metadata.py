#!/usr/bin/env python3
"""Create RAG jurisdiction metadata using MCP SDK.

Matches included regulations to documents and creates jurisdiction_code metadata
for each RAG file. Supports checkpoint-based resumption and handles false negative
INTERNAL errors from the create_rag_metadata tool.

Usage:
    python3 create_rag_jurisdiction_metadata.py --config <mcp_config.json>
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession
from mcp.client.sse import sse_client

# Configuration
WORKSPACE_ID = 1
REPOSITORY_ID = 6
PROGRESS_FILE = Path("orca/assets/rag_meta_batch_progress.json")
BATCH_SIZE = 100
BATCH_DIR = Path("orca/assets")

def load_progress():
    """Load progress state or return defaults."""
    if not PROGRESS_FILE.exists():
        return _default_progress()
    try:
        return json.loads(PROGRESS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        print("Warning: Progress file corrupted, starting fresh")
        return _default_progress()

def _default_progress():
    return {
        "current_batch": None,
        "current_batch_index": 0,
        "completed_entries": 0,
        "total_entries": 0,
        "last_updated": None,
    }

def save_progress(state):
    """Save progress atomically with UTC timestamp."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    temp = PROGRESS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2))
    temp.rename(PROGRESS_FILE)

async def get_mcp_session(config):
    """Yield an initialized MCP session via HTTP/SSE."""
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    async with sse_client(url=config["url"], headers=config.get("headers", {})) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            yield session

def load_entries(path):
    """Return the 'files' list from a batch JSON file."""
    return json.loads(path.read_text()).get("files", [])

async def fetch_regulations(session):
    """Return included regulations for the workspace."""
    print("Fetching regulations...")
    result = await session.call_tool("list_regulations", {"workspaceId": WORKSPACE_ID, "limit": 2**31 - 1})
    regs = result.content.get("regulations", [])
    included = [r for r in regs if r.get("included")]
    print(f"Found {len(included)} included regulations out of {len(regs)} total")
    return included

async def fetch_documents(session):
    """Return a map of filename → rag_file_name."""
    print("Fetching documents...")
    result = await session.call_tool("list_documents", {"workspaceId": WORKSPACE_ID, "repositoryId": REPOSITORY_ID, "limit": 2**31 - 1})
    docs = result.content.get("documents", [])
    doc_map = {}
    for doc in docs:
        fname = doc.get("filename")
        rag = doc.get("rag_file_name")
        if fname and rag:
            doc_map[fname] = rag
    print(f"Built document map with {len(doc_map)} entries")
    return doc_map

def match_regulations(regs, doc_map):
    """Build metadata entries by matching regulations to documents."""
    matches = []
    missing = 0
    for reg in regs:
        code = reg.get("jurisdiction", {}).get("code")
        if not code:
            continue
        for fname in reg.get("filenames", []):
            rag = doc_map.get(fname)
            if rag:
                matches.append({"ragFileName": rag, "entries": [{"key": "jurisdiction_code", "valueStr": code}]})
            else:
                missing += 1
    print(f"Total matches: {len(matches)}, Missing documents: {missing}")
    return matches

def save_batches(matches):
    """Write matches to batch JSON files and return their paths."""
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batches = (len(matches) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Generating {batches} batch files in {BATCH_DIR}...")
    paths = []
    for i in range(0, len(matches), BATCH_SIZE):
        num = i // BATCH_SIZE + 1
        chunk = matches[i : i + BATCH_SIZE]
        path = BATCH_DIR / f"rag_meta_batch_{num}.json"
        path.write_text(json.dumps({"files": chunk}, indent=2))
        paths.append(path)
        print(f"  Created {path.name} with {len(chunk)} entries")
    return paths

async def check_metadata(session, rag):
    """Return existing jurisdiction_code value or None."""
    try:
        result = await session.call_tool("list_rag_metadata", {"ragFileName": rag})
        for entry in result.content.get("metadataEntries", []):
            if entry.get("key") == "jurisdiction_code":
                return entry.get("valueStr")
    except Exception as e:
        print(f"    Warning: Failed to check metadata: {e}")
    return None

async def upsert_metadata(session, rag, entries, expected):
    """Create or update metadata after checking existing state.
    
    Returns (success: bool, message: str).
    """
    current = await check_metadata(session, rag)
    if current == expected:
        return True, "Skipped"

    try:
        tool = "create_rag_metadata" if current is None else "update_rag_metadata"
        result = await session.call_tool(tool, {"ragFileName": rag, "entries": entries})

        # Handle false-negative INTERNAL errors
        if result.isError and "INTERNAL" in str(result.content):
            verified = await check_metadata(session, rag)
            if verified == expected:
                return True, "Created & Verified (false negative)"
            return False, "Failed verification after INTERNAL error"

        # Normal verification for updates
        if current is not None:
            verified = await check_metadata(session, rag)
            if verified != expected:
                return False, f"Verification mismatch: expected {expected}, got {verified}"

        return True, "Created" if current is None else "Updated"
    except Exception as e:
        return False, f"Exception: {e}"

async def process_batches(session, batch_paths, total):
    """Process batch files with checkpoint resumption."""
    progress = load_progress()
    progress["total_entries"] = total
    start_batch = progress["current_batch"]
    start_idx = progress["current_batch_index"]
    resume = start_batch is None

    for path in batch_paths:
        name = path.name
        if not resume:
            if name == start_batch:
                resume = True
            else:
                print(f"Skipping completed batch: {name}")
                continue

        print(f"\nProcessing: {name}")
        entries = load_entries(path)
        idx = start_idx if name == start_batch else 0

        for i in range(idx, len(entries)):
            entry = entries[i]
            ok, msg = await upsert_metadata(session, entry["ragFileName"], entry["entries"], entry["entries"][0]["valueStr"])
            if ok:
                progress["completed_entries"] += 1
            else:
                print(f"    Failed: {entry['ragFileName']} - {msg}")

            if (i - idx + 1) % 10 == 0:
                progress.update({"current_batch": name, "current_batch_index": i + 1})
                save_progress(progress)
                print(f"  Progress: {progress['completed_entries']}/{total}")

        progress.update({"current_batch": name, "current_batch_index": 0})
        save_progress(progress)
        print(f"Batch {name} complete")

    return progress

async def main():
    parser = argparse.ArgumentParser(description="Create RAG jurisdiction metadata")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    async for session in get_mcp_session(config):
        regs = await fetch_regulations(session)
        doc_map = await fetch_documents(session)
        matches = match_regulations(regs, doc_map)
        if not matches:
            print("No matches found.")
            return

        batch_paths = save_batches(matches)
        progress = await process_batches(session, batch_paths, len(matches))

    rate = (progress["completed_entries"] / progress["total_entries"] * 100) if progress["total_entries"] else 0
    print(f"\n{'='*60}\nCOMPLETE\n{'='*60}")
    print(f"Processed: {progress['completed_entries']}/{progress['total_entries']} ({rate:.1f}%)")

if __name__ == "__main__":
    asyncio.run(main())
