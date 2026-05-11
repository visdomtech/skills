#!/usr/bin/env python3
"""
Create RAG Jurisdiction Metadata using MCP SDK

This script creates jurisdiction_code metadata for RAG files by matching included
regulations to their corresponding documents in the Compliance Repository.
It uses the MCP Python SDK to call Orca MCP tools directly with checkpoint-based
resumption and false negative error handling.

Usage:
    python3 create_rag_jurisdiction_metadata.py --config <path_to_mcp_config.json>

Options:
    --config PATH   Path to MCP server configuration JSON file (required)
                    Example config:
                    {
                      "type": "http",
                      "url": "https://orcaservices-360095844563.us-central1.run.app",
                      "headers": {
                        "X-API-KEY": "your-api-key-here"
                      }
                    }
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from mcp import ClientSession
from mcp.client.sse import sse_client

# --- Configuration ---
WORKSPACE_ID = 1
REPOSITORY_ID = 6
PROGRESS_FILE = Path("orca/assets/rag_meta_batch_progress.json")
BATCH_SIZE = 100
CACHE_DIR = Path("orca/assets")

# --- Progress tracking ---
def load_progress():
    """Load progress state from file, or return empty state if not exists."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            print(f"Warning: Progress file corrupted, starting fresh")
    return {
        "current_batch": None,
        "current_batch_index": 0,
        "completed_entries": 0,
        "total_entries": 0,
        "last_updated": None
    }

def save_progress(state):
    """Save progress state to file atomically with timestamp."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    temp_file = PROGRESS_FILE.with_suffix('.tmp')
    temp_file.write_text(json.dumps(state, indent=2))
    temp_file.rename(PROGRESS_FILE)

# --- MCP client setup ---
async def get_mcp_session(mcp_config: dict):
    """Connect to MCP server via HTTP/SSE transport."""
    if mcp_config.get("type") != "http":
        raise ValueError(f"Unsupported transport type: {mcp_config['type']}. Only 'http' is supported.")
    
    async with sse_client(
        url=mcp_config["url"],
        headers=mcp_config.get("headers", {}),
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

# --- Batch file helper ---
def load_entries(batch_file: Path) -> list:
    """Load entries from a batch file."""
    with open(batch_file, 'r') as f:
        data = json.load(f)
    return data.get('files', [])

# --- Data fetching ---
async def fetch_regulations(session, workspace_id: int):
    """Fetch all regulations and filter to included only."""
    print("Fetching regulations...")
    result = await session.call_tool(
        "list_regulations",
        arguments={"workspaceId": workspace_id, "limit": 2147483647}
    )
    regulations = result.content.get('regulations', [])
    included_regs = [r for r in regulations if r.get('included')]
    print(f"Found {len(included_regs)} included regulations out of {len(regulations)} total")
    return included_regs

async def fetch_documents(session, workspace_id: int, repository_id: int):
    """Fetch all documents and build filename->rag_file_name map."""
    print("Fetching documents...")
    result = await session.call_tool(
        "list_documents",
        arguments={"workspaceId": workspace_id, "repositoryId": repository_id, "limit": 2147483647}
    )
    documents = result.content.get('documents', [])
    
    doc_map = {}
    for doc in documents:
        fname = doc.get('filename')
        rag_name = doc.get('rag_file_name')
        if fname and rag_name:
            doc_map[fname] = rag_name
    
    print(f"Built document map with {len(doc_map)} entries")
    return doc_map

# --- Metadata matching ---
def match_regulations_to_documents(included_regs, doc_map):
    """Match regulations to documents and build metadata entries."""
    matches = []
    missing_count = 0
    
    for reg in included_regs:
        jurisdiction_code = reg.get('jurisdiction', {}).get('code')
        filenames = reg.get('filenames', [])
        
        if not jurisdiction_code:
            continue
        
        for fname in filenames:
            rag_name = doc_map.get(fname)
            if rag_name:
                matches.append({
                    "ragFileName": rag_name,
                    "entries": [
                        {"key": "jurisdiction_code", "valueStr": jurisdiction_code}
                    ]
                })
            else:
                missing_count += 1
    
    print(f"Total matches found: {len(matches)}")
    print(f"Missing documents: {missing_count}")
    return matches

# --- Batch file generation ---
def save_batch_files(matches, cache_dir: Path):
    """Save matches to intermediate batch files in cache directory."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    total_batches = (len(matches) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"Generating {total_batches} batch files in {cache_dir}...")
    
    batch_files = []
    for i in range(0, len(matches), BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch_content = {
            "files": matches[i:i + BATCH_SIZE]
        }
        
        batch_file = cache_dir / f"rag_meta_batch_{batch_num}.json"
        with open(batch_file, 'w') as f:
            json.dump(batch_content, f, indent=2)
        
        batch_files.append(batch_file)
        print(f"  Created {batch_file.name} with {len(batch_content['files'])} entries")
    
    return batch_files

# --- Metadata processing ---
async def check_existing_metadata(session, rag_file_name: str):
    """Check if jurisdiction_code metadata already exists for a RAG file."""
    try:
        result = await session.call_tool(
            "list_rag_metadata",
            arguments={"ragFileName": rag_file_name}
        )
        metadata_list = result.content.get('metadataEntries', [])
        for entry in metadata_list:
            if entry.get('key') == 'jurisdiction_code':
                return entry.get('valueStr')
        return None
    except Exception as e:
        print(f"    Warning: Failed to check metadata: {e}")
        return None

async def create_or_update_metadata(session, rag_file_name: str, entries: list, expected_value: str):
    """
    Create or update metadata based on existing state.
    Returns tuple: (success: bool, action: str)
    """
    # Check existing metadata
    existing_value = await check_existing_metadata(session, rag_file_name)
    
    if existing_value == expected_value:
        return True, "Skipped (Match)"
    
    try:
        if existing_value is None:
            # Key missing - create
            result = await session.call_tool(
                "create_rag_metadata",
                arguments={"ragFileName": rag_file_name, "entries": entries}
            )
            
            # Handle false negative INTERNAL errors
            if result.isError and "INTERNAL" in str(result.content):
                print(f"    Warning: INTERNAL error - verifying...")
                verify_value = await check_existing_metadata(session, rag_file_name)
                if verify_value == expected_value:
                    return True, "Created & Verified (false negative handled)"
                else:
                    return False, "Failed (verification mismatch after INTERNAL error)"
            
            return True, "Created"
        else:
            # Key exists with different value - update
            result = await session.call_tool(
                "update_rag_metadata",
                arguments={"ragFileName": rag_file_name, "entries": entries}
            )
            
            # Verify update
            verify_value = await check_existing_metadata(session, rag_file_name)
            if verify_value == expected_value:
                return True, "Updated & Verified"
            else:
                return False, f"Failed (verification mismatch: expected {expected_value}, got {verify_value})"
    
    except Exception as e:
        return False, f"Failed (exception: {str(e)})"

# --- Main processing logic ---
async def process_batch_files(session, batch_files: list, total_entries: int):
    """Process batch files with checkpoint-based resumption."""
    progress = load_progress()
    progress["total_entries"] = total_entries
    
    # Determine starting point
    start_batch = progress["current_batch"]
    start_index = progress["current_batch_index"]
    
    found_start = start_batch is None
    
    for batch_file in batch_files:
        batch_filename = batch_file.name
        
        # Skip batches before resume point
        if not found_start:
            if batch_filename == start_batch:
                found_start = True
            else:
                print(f"Skipping completed batch: {batch_filename}")
                continue
        
        print(f"\nProcessing: {batch_filename}")
        entries = load_entries(batch_file)
        
        # Start from saved index within this batch
        start_idx = start_index if batch_filename == start_batch else 0
        
        for i in range(start_idx, len(entries)):
            entry = entries[i]
            rag_file_name = entry["ragFileName"]
            expected_value = entry["entries"][0]["valueStr"]
            
            success, action = await create_or_update_metadata(
                session, rag_file_name, entry["entries"], expected_value
            )
            
            if success:
                progress["completed_entries"] += 1
            else:
                print(f"    Failed: {rag_file_name} - {action}")
            
            # Update progress every 10 entries
            if (i - start_idx + 1) % 10 == 0:
                progress["current_batch"] = batch_filename
                progress["current_batch_index"] = i + 1
                save_progress(progress)
                print(f"  Progress: {progress['completed_entries']}/{total_entries}")
        
        # Batch complete - reset index for next batch
        progress["current_batch"] = batch_filename
        progress["current_batch_index"] = 0
        save_progress(progress)
        print(f"Batch {batch_filename} complete")
    
    return progress

# --- Main entry point ---
async def main():
    parser = argparse.ArgumentParser(description='Create RAG jurisdiction metadata using MCP SDK')
    parser.add_argument('--config', required=True, help='Path to MCP server configuration JSON file')
    args = parser.parse_args()
    
    # Load MCP config
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        mcp_config = json.load(f)
    
    print(f"Loaded MCP config from {config_path}")
    print(f"Server URL: {mcp_config.get('url')}")
    
    async for session in get_mcp_session(mcp_config):
        # Step 1: Fetch data
        included_regs = await fetch_regulations(session, WORKSPACE_ID)
        doc_map = await fetch_documents(session, WORKSPACE_ID, REPOSITORY_ID)
        
        # Step 2: Match regulations to documents
        matches = match_regulations_to_documents(included_regs, doc_map)
        
        if not matches:
            print("No matches found. Exiting.")
            return
        
        # Step 3: Save intermediate batch files to cache
        batch_files = save_batch_files(matches, CACHE_DIR)
        total_entries = len(matches)
        
        # Step 4: Process batch files with MCP tools
        progress = await process_batch_files(session, batch_files, total_entries)
    
    # Final summary
    print(f"\n{'='*60}")
    print("PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Total processed: {progress['completed_entries']}")
    print(f"Total entries: {progress['total_entries']}")
    print(f"Success rate: {(progress['completed_entries'] / progress['total_entries'] * 100):.2f}%" if progress['total_entries'] > 0 else "N/A")

if __name__ == "__main__":
    asyncio.run(main())
