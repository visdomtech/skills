#!/usr/bin/env python3
"""Fetch law changes via MCP SDK and generate HTML report.

Usage:
    python3 fetch_law_changes.py --config <mcp_config.json> [--since-date YYYY-MM-DD]
                                 [--change-type <type>] [--jurisdiction <code>]
                                 [--output <report.html>] [--date-label <label>]
"""

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ASSETS_DIR = Path("orca/assets")
LAW_CHANGES_FILE = ASSETS_DIR / "law_changes.json"
DEFAULT_OUTPUT = ASSETS_DIR / "law_changes_report.html"
GENERATE_SCRIPT = Path("orca/scripts/law_changes_report/generate_law_changes_report.py")


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
    client = httpx.AsyncClient(headers=config.get("headers", {}))
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


async def fetch_law_changes(config, since_date, change_type=None, jurisdiction=None):
    print(f"Fetching law changes since {since_date}...")
    args = {"sinceDate": since_date}
    if change_type:
        args["changeType"] = change_type
    if jurisdiction:
        args["jurisdiction"] = jurisdiction

    async for session in get_mcp_session(config):
        result = await session.call_tool("get_latest_law_changes", args)
        content = _parse_content(result)
        changes = content.get("changes", [])
        print(f"Fetched {len(changes)} law changes")
        return changes


async def main():
    parser = argparse.ArgumentParser(description="Fetch law changes and generate report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--since-date", help="Fetch changes since this date (YYYY-MM-DD). Defaults to 7 days ago.")
    parser.add_argument("--change-type", help="Filter by change type: Amendment, New Law, or Update")
    parser.add_argument("--jurisdiction", help="Filter by jurisdiction code (e.g. US-CA)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file path")
    parser.add_argument("--date-label", help="Date range label for the report header")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    since_date = args.since_date
    if not since_date:
        since_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        print(f"No --since-date provided; defaulting to 7 days ago: {since_date}")

    changes = await fetch_law_changes(config, since_date, args.change_type, args.jurisdiction)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"changes": changes, "count": len(changes)}
    LAW_CHANGES_FILE.write_text(json.dumps(payload, indent=2))
    print(f"Saved {len(changes)} changes to {LAW_CHANGES_FILE}")

    date_label = args.date_label or f"Since {since_date}"
    output_path = Path(args.output)

    print(f"\nGenerating report...")
    result = subprocess.run(
        [sys.executable, str(GENERATE_SCRIPT), str(LAW_CHANGES_FILE), str(output_path), date_label],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"Report generation failed (exit code {result.returncode})")
        raise SystemExit(result.returncode)

    print(f"\nDone. Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
