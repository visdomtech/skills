"""Shared utilities for RAG metadata upsert operations."""

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content


async def get_current_value(session, rag_file_name, key):
    """Return the current metadata value for key on the RAG file, or None if absent."""
    result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file_name})
    content = _parse_content(result)
    for entry in (content.get("metadata") or []):
        if entry.get("key") == key:
            return entry.get("value")
    return None


async def upsert_rag_metadata(session, rag_file_name, key, value, firestore_client=None):
    """Create or update a single RAG metadata key-value pair.

    Returns (status, detail) where status is one of:
        "created"  — metadata key was absent and has been written
        "updated"  — metadata key existed with a different value and has been updated
        "skipped"  — metadata key already had the expected value; no write performed
        "failed"   — write failed and could not be verified

    When firestore_client is provided, a Firestore cache fast-path is attempted
    before hitting the MCP API, and results are cached after MCP reads.
    """
    # Firestore cache fast-path (skip MCP read if cache confirms current value)
    if firestore_client:
        from scripts.common.firestore_utils import get_rag_metadata, save_rag_metadata
        filename = rag_file_name.split("/")[-1] if "/" in rag_file_name else rag_file_name
        try:
            cached = await get_rag_metadata(firestore_client, filename)
            if cached:
                for entry in (cached.get("metadata") or []):
                    if entry.get("key") == key and entry.get("value") == value:
                        return "skipped", "cache confirmed"
        except Exception as e:
            print(f"    Warning: Firestore cache read failed for {filename}: {e}", flush=True)

    # Read current value from MCP
    try:
        result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_file_name})
        content = _parse_content(result)
        entries = content.get("metadata") or []
        current = None
        for entry in entries:
            if entry.get("key") == key:
                current = entry.get("value")
                break

        # Cache MCP read result in Firestore
        if firestore_client:
            try:
                filename = rag_file_name.split("/")[-1] if "/" in rag_file_name else rag_file_name
                from scripts.common.firestore_utils import save_rag_metadata
                await save_rag_metadata(
                    client=firestore_client,
                    rag_file_name=rag_file_name,
                    filename=filename,
                    metadata=entries,
                )
            except Exception as e:
                print(f"    Warning: Firestore cache write failed: {e}", flush=True)

    except Exception as e:
        return "failed", f"list_rag_metadata failed: {e}"

    if current == value:
        return "skipped", None

    # Write
    try:
        tool = "create_rag_metadata" if current is None else "update_rag_metadata"
        write_result = await session.call_tool(
            tool, {"ragFileName": rag_file_name, "entries": [{"key": key, "valueStr": value}]}
        )

        if write_result.isError:
            err_text = str(write_result.content)
            if "INTERNAL" in err_text:
                # Re-verify — MCP often returns INTERNAL on success
                verified = await get_current_value(session, rag_file_name, key)
                if verified == value:
                    action = "created" if current is None else "updated"
                    return action, "false-negative INTERNAL"
            return "failed", err_text

        # Post-update verification for updates (creates are implicitly verified above)
        if current is not None:
            verified = await get_current_value(session, rag_file_name, key)
            if verified != value:
                return "failed", f"verification mismatch: expected {value!r}, got {verified!r}"

        action = "created" if current is None else "updated"
        return action, None

    except Exception as e:
        return "failed", str(e)
