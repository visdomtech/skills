#!/usr/bin/env python3
"""Sync RAG metadata cache for a specific document.

Updates the `rag_metadata_cache` collection in Firestore for a given document
after its metadata has been updated in Vertex AI via MCP tools.

Usage:
    uv run rag-metadata-sync-cache --config assets/mcp_config.json --filename "my_doc.pdf" --key "jurisdiction_code" --value "US-CA"
"""

import argparse
import asyncio

from scripts.common.firestore_utils import (
    get_firestore_client,
    get_rag_metadata,
    save_rag_metadata,
)
from scripts.common.utils import load_documents, load_mcp_config


async def sync_cache(filename, key, new_value):
    """Sync a single metadata entry for a document in Firestore cache."""
    client = get_firestore_client()
    try:
        # Find rag_file_name from cached documents
        documents = load_documents()
        rag_file_name = None
        for doc in documents:
            if doc.get("filename") == filename:
                rag_file_name = doc.get("rag_file_name")
                break

        if not rag_file_name:
            print(f"Warning: Could not find rag_file_name for {filename}. Using empty string.")
            rag_file_name = ""

        # Get existing cache
        cached = await get_rag_metadata(client, filename)
        metadata = cached["metadata"] if cached else []

        # Update or add the key
        updated = False
        for entry in metadata:
            if entry.get("key") == key:
                entry["value"] = new_value
                updated = True
                break

        if not updated:
            metadata.append({"key": key, "value": new_value})

        # Save back to Firestore
        await save_rag_metadata(
            client=client,
            rag_file_name=rag_file_name,
            filename=filename,
            metadata=metadata,
        )
        print(f"Successfully synced metadata for {filename}: {key}={new_value}")
    finally:
        client.close()


async def main():
    parser = argparse.ArgumentParser(description="Sync RAG metadata cache for a document")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON (used for context)")
    parser.add_argument("--filename", required=True, help="Filename of the document to sync")
    parser.add_argument("--key", required=True, help="Metadata key to update")
    parser.add_argument("--value", required=True, help="New value for the metadata key")
    args = parser.parse_args()

    load_mcp_config(args.config)

    await sync_cache(args.filename, args.key, args.value)


def cli():
    """Entry point for the console script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
