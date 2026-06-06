#!/usr/bin/env python3
"""Fetch regulations via MCP SDK and produce a summary.

Usage:
    python3 fetch_regulations.py --config <mcp_config.json>
        [--workspace-id <id>] [--output <path>]
"""

import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from scripts.common.tools.mcp_wrapper_base import get_mcp_session, _parse_content
from scripts.common.utils import load_mcp_config


ASSETS_DIR = Path("assets")
DEFAULT_OUTPUT = ASSETS_DIR / "regulations_summary.json"
REGULATIONS_FILE = ASSETS_DIR / "regulations.json"


async def fetch_regulations(config, workspace_id: int):
    print(f"Fetching regulations for workspace {workspace_id}...")
    async with get_mcp_session(config) as session:
        result = await session.call_tool(
            "list_regulations",
            {"workspaceId": workspace_id, "limit": 2**31 - 1},
        )
        content = _parse_content(result)
        regulations = content.get("regulations", [])
        print(f"Fetched {len(regulations)} regulations")
        return regulations


def _get_jurisdiction_key(r: dict) -> str:
    jurisdiction = r.get("jurisdiction")
    if isinstance(jurisdiction, dict):
        return jurisdiction.get("code") or jurisdiction.get("name") or str(jurisdiction)
    return jurisdiction


def _get_categories(r: dict) -> list[str]:
    reg = r.get("regulation") or {}
    cats = reg.get("categories")
    return cats if isinstance(cats, list) else []


def summarize(regulations: list[dict]) -> dict:
    total = len(regulations)
    by_category = Counter()
    for r in regulations:
        for cat in _get_categories(r):
            by_category[cat] += 1
    by_jurisdiction = Counter(_get_jurisdiction_key(r) for r in regulations)
    by_included = Counter(r.get("included") for r in regulations)

    return {
        "total": total,
        "by_category": dict(by_category),
        "by_jurisdiction": dict(by_jurisdiction),
        "by_included": {str(k): v for k, v in by_included.items()},
    }


def print_summary(summary: dict):
    print("\n=== Regulations Summary ===")
    print(f"Total: {summary['total']}")

    print("\nBy Category:")
    for category, count in sorted(summary["by_category"].items(), key=lambda x: -x[1]):
        print(f"  {category}: {count}")

    print("\nBy Jurisdiction:")
    for jurisdiction, count in sorted(summary["by_jurisdiction"].items(), key=lambda x: -x[1]):
        print(f"  {jurisdiction}: {count}")

    print("\nBy Included:")
    for included, count in sorted(summary["by_included"].items(), key=lambda x: -x[1]):
        print(f"  {included}: {count}")


async def async_main():
    parser = argparse.ArgumentParser(description="Fetch regulations and summarize")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=1,
        help="Workspace ID to list regulations for (default: 1)",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output summary JSON file path",
    )
    args = parser.parse_args()

    config = load_mcp_config(args.config)
    print(f"Config loaded (URL: {config.get('url')})")

    regulations = await fetch_regulations(config, args.workspace_id)
    if not regulations:
        print("No regulations returned.")
        summary = {"total": 0, "by_category": {}, "by_jurisdiction": {}, "by_included": {}}
    else:
        summary = summarize(regulations)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # Save raw regulations
    payload = {"regulations": regulations, "count": len(regulations)}
    REGULATIONS_FILE.write_text(json.dumps(payload, indent=2))
    print(f"Saved {len(regulations)} regulations to {REGULATIONS_FILE}")

    # Save and print summary
    output_path = Path(args.output)
    output_path.write_text(json.dumps(summary, indent=2))
    print(f"Saved summary to {output_path}")
    print_summary(summary)


def main():
    """Entry point for console script (uv handles asyncio)."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
