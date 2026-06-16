"""Common utilities used across Orca scripts."""

import json
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import _parse_content


COMPLIANCE_DOCUMENTS_FILE = Path("assets/compliance_documents.json")


def load_mcp_config(config_path: str | Path) -> dict:
    """Load and validate an MCP server configuration from a JSON file.

    Args:
        config_path: Path to the JSON config file.

    Returns:
        The parsed configuration dictionary.

    Raises:
        SystemExit: If the config file does not exist.
    """
    path = Path(config_path)
    if not path.exists():
        print(f"Error: Config not found: {path}")
        raise SystemExit(1)
    return json.loads(path.read_text())


def load_documents(documents_file: str | Path | None = None) -> list[dict]:
    """Load documents from a cached JSON file.

    Supports the cache-wrapper format produced by the MCP SDK:
      ``{"response": {"data": {"documents": [...]}}}``
    as well as the flat format:
      ``{"documents": [...]}``

    Args:
        documents_file: Path to the JSON file. Defaults to
            ``assets/compliance_documents.json``.

    Returns:
        List of document dictionaries. Empty list if no documents found.

    Raises:
        SystemExit: If the file does not exist.
    """
    path = Path(documents_file) if documents_file else COMPLIANCE_DOCUMENTS_FILE
    if not path.exists():
        print(f"Error: Documents file not found: {path}. Run fetch-compliance-documents first.")
        raise SystemExit(1)

    data = json.loads(path.read_text())
    if "response" in data and "data" in data["response"]:
        return data["response"]["data"].get("documents", [])
    return data.get("documents", [])


# ---------------------------------------------------------------------------
# Reusable async MCP-fetching helpers
# ---------------------------------------------------------------------------

async def fetch_workspaces(session) -> list[dict]:
    """Call list_workspaces via the MCP session and return the workspaces list."""
    result = await session.call_tool("list_workspaces", {})
    content = _parse_content(result)
    return content.get("workspaces", [])


async def fetch_repositories(session, workspace_id: int) -> list[dict]:
    """Call list_repositories for a given workspace and return the repositories list."""
    result = await session.call_tool("list_repositories", {"workspaceId": workspace_id})
    content = _parse_content(result)
    return content.get("repositories", [])


async def fetch_documents(session, workspace_id: int, repository_id: int) -> tuple[list[dict], dict]:
    """Call list_documents and return (documents_list, raw_response_dict).

    Uses limit=2**31-1 to fetch all documents.
    """
    result = await session.call_tool("list_documents", {
        "workspaceId": workspace_id,
        "repositoryId": repository_id,
        "limit": 2**31 - 1,
    })
    content = _parse_content(result)
    documents = content.get("documents", [])
    return documents, content
