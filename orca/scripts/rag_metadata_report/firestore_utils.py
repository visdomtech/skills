#!/usr/bin/env python3
"""Firestore async client utilities for RAG metadata caching."""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from google.cloud import firestore

# Firestore collection name
RAG_METADATA_COLLECTION = "rag_metadata_cache"


def get_firestore_client(project_id: Optional[str] = "visdomapp-1") -> firestore.AsyncClient:
    return firestore.AsyncClient(project=project_id, database="regulations")


def _get_document_ref(client: firestore.AsyncClient, filename: str) -> firestore.AsyncDocumentReference:
    return client.collection(RAG_METADATA_COLLECTION).document(filename)


async def save_rag_metadata(
    client: firestore.AsyncClient,
    rag_file_name: str,
    filename: str,
    metadata: List[Dict[str, str]],
    document_data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    doc_ref = _get_document_ref(client, filename)

    data = {
        "rag_file_name": rag_file_name,
        "filename": filename,
        "metadata": metadata or [],
        "cached_at": datetime.now(timezone.utc),
        "error": error,
    }

    if document_data:
        data["document_data"] = document_data

    await doc_ref.set(data, merge=True)


async def get_rag_metadata(
    client: firestore.AsyncClient,
    filename: str,
) -> Optional[Dict[str, Any]]:
    doc_ref = _get_document_ref(client, filename)
    doc = await doc_ref.get()

    if not doc.exists:
        return None

    data = doc.to_dict()
    return {
        "filename": data.get("filename", ""),
        "rag_file_name": data.get("rag_file_name", ""),
        "metadata": data.get("metadata", []),
        "document_data": data.get("document_data"),
        "error": data.get("error"),
        "cached_at": data.get("cached_at"),
    }


async def batch_save_rag_metadata(
    client: firestore.AsyncClient,
    results: List[Dict[str, Any]],
) -> int:
    batch = client.batch()
    count = 0

    for res in results:
        filename = res.get("filename", "")
        if not filename:
            continue

        doc_ref = _get_document_ref(client, filename)

        data = {
            "rag_file_name": res.get("rag_file_name", ""),
            "filename": filename,
            "metadata": res.get("metadata", []),
            "cached_at": datetime.now(timezone.utc),
            "error": res.get("error"),
        }

        batch.set(doc_ref, data, merge=True)
        count += 1

    await batch.commit()
    return count


RAG_METADATA_SUMMARY_COLLECTION = "rag_metadata_summary"
JURISDICTION_CODES_DOCUMENT = "jurisdiction_codes"


async def save_jurisdiction_codes(client: firestore.AsyncClient, codes: set) -> None:
    doc_ref = client.collection(RAG_METADATA_SUMMARY_COLLECTION).document(JURISDICTION_CODES_DOCUMENT)
    await doc_ref.set({
        "codes": sorted(codes),
        "count": len(codes),
        "updated_at": datetime.now(timezone.utc),
    })


async def get_jurisdiction_codes(client: firestore.AsyncClient) -> Optional[List[str]]:
    doc_ref = client.collection(RAG_METADATA_SUMMARY_COLLECTION).document(JURISDICTION_CODES_DOCUMENT)
    doc = await doc_ref.get()
    if not doc.exists:
        return None
    return doc.to_dict().get("codes", [])


async def clear_cache_for_workspace(
    client: firestore.AsyncClient,
    workspace_id: int,
    repository_id: int,
) -> int:
    collection = client.collection(RAG_METADATA_COLLECTION)
    query = collection.where("document_data.ws", "==", workspace_id)
    query = query.where("document_data.repository_id", "==", repository_id)

    count = 0
    batch = client.batch()

    async for doc in query.stream():
        batch.delete(doc.reference)
        count += 1

    if count > 0:
        await batch.commit()

    return count
