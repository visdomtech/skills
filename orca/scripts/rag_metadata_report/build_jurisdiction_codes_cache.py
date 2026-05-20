#!/usr/bin/env python3
"""Build jurisdiction codes cache from rag_metadata_cache collection.

Scans all documents in the rag_metadata_cache Firestore collection and
aggregates distinct jurisdiction_code values into a single summary document at
rag_metadata_summary/jurisdiction_codes.
"""

import asyncio

from scripts.common.firestore_utils import (
    RAG_METADATA_COLLECTION,
    get_firestore_client,
    save_jurisdiction_codes,
)


async def _build():
    client = get_firestore_client()
    try:
        codes: set[str] = set()
        total = 0
        async for doc in client.collection(RAG_METADATA_COLLECTION).stream():
            data = doc.to_dict()
            for entry in data.get("metadata", []):
                if entry.get("key") == "jurisdiction_code" and entry.get("value"):
                    codes.add(entry["value"])
            total += 1
            if total % 100 == 0:
                print(f"Scanned {total} documents...", flush=True)

        print(f"Scanned {total} total documents. Found {len(codes)} distinct jurisdiction codes.")
        await save_jurisdiction_codes(client, codes)
        print(f"Saved to rag_metadata_summary/jurisdiction_codes: {sorted(codes)}")
    finally:
        client.close()


def main():
    asyncio.run(_build())


if __name__ == "__main__":
    main()
