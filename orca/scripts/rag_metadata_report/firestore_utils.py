#!/usr/bin/env python3
"""Firestore client utilities for RAG metadata caching."""

import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from google.cloud import firestore


# Firestore collection name
RAG_METADATA_COLLECTION = "rag_metadata_cache"


def get_firestore_client(project_id: Optional[str] = "visdomapp-1") -> firestore.Client:
    return firestore.Client(project=project_id, database="regulations")


def _get_document_ref(client: firestore.Client, rag_file_name: str) -> firestore.DocumentReference:
    """Get Firestore document reference for a RAG file.
    
    Uses the RAG file resource name as the document ID (with special characters escaped).
    
    Args:
        client: Firestore client instance.
        rag_file_name: Full RAG file resource name.
    
    Returns:
        Document reference.
    """
    # Use the last segment of the RAG file name as document ID for simplicity
    # Format: projects/{project}/locations/{location}/ragCorpora/{corpus}/ragFiles/{file_id}
    doc_id = rag_file_name.split("/")[-1]
    return client.collection(RAG_METADATA_COLLECTION).document(doc_id)


def save_rag_metadata(
    client: firestore.Client,
    rag_file_name: str,
    filename: str,
    metadata: List[Dict[str, str]],
    document_data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Save RAG metadata to Firestore.
    
    Args:
        client: Firestore client instance.
        rag_file_name: Full RAG file resource name.
        filename: Original document filename.
        metadata: List of metadata entries (each with 'key' and 'value').
        document_data: Optional original document data from MCP.
        error: Optional error message if fetching failed.
    """
    doc_ref = _get_document_ref(client, rag_file_name)
    
    data = {
        "rag_file_name": rag_file_name,
        "filename": filename,
        "metadata": metadata or [],
        "cached_at": datetime.now(timezone.utc),
        "error": error,
    }
    
    if document_data:
        data["document_data"] = document_data
    
    # Use merge to update existing documents without overwriting other fields
    doc_ref.set(data, merge=True)


def get_rag_metadata(
    client: firestore.Client,
    rag_file_name: str,
) -> Optional[Dict[str, Any]]:
    """Retrieve RAG metadata from Firestore cache.
    
    Args:
        client: Firestore client instance.
        rag_file_name: Full RAG file resource name.
    
    Returns:
        Dictionary with cached data if found, None otherwise.
    """
    doc_ref = _get_document_ref(client, rag_file_name)
    doc = doc_ref.get()
    
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


def batch_save_rag_metadata(
    client: firestore.Client,
    results: List[Dict[str, Any]],
) -> int:
    """Batch save multiple RAG metadata entries to Firestore.
    
    Args:
        client: Firestore client instance.
        results: List of result dictionaries from fetch operations.
    
    Returns:
        Number of documents saved.
    """
    batch = client.batch()
    count = 0
    
    for res in results:
        rag_file_name = res.get("rag_file_name", "")
        if not rag_file_name:
            continue
        
        doc_ref = _get_document_ref(client, rag_file_name)
        
        data = {
            "rag_file_name": rag_file_name,
            "filename": res.get("filename", ""),
            "metadata": res.get("metadata", []),
            "cached_at": datetime.now(timezone.utc),
            "error": res.get("error"),
        }
        
        batch.set(doc_ref, data, merge=True)
        count += 1
    
    batch.commit()
    return count


def clear_cache_for_workspace(
    client: firestore.Client,
    workspace_id: int,
    repository_id: int,
) -> int:
    """Clear cached metadata for a specific workspace/repository.
    
    Args:
        client: Firestore client instance.
        workspace_id: Workspace ID.
        repository_id: Repository ID.
    
    Returns:
        Number of documents deleted.
    """
    # Query documents by workspace/repository in document_data
    collection = client.collection(RAG_METADATA_COLLECTION)
    query = collection.where("document_data.ws", "==", workspace_id)
    query = query.where("document_data.repository_id", "==", repository_id)
    
    docs = query.stream()
    count = 0
    batch = client.batch()
    
    for doc in docs:
        batch.delete(doc.reference)
        count += 1
    
    if count > 0:
        batch.commit()
    
    return count
