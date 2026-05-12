#!/usr/bin/env python3
"""Fetch jurisdictions via MCP SDK and generate HTML report.

Usage:
    python3 fetch_jurisdictions.py --config <mcp_config.json> [--output <report.html>]
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


ASSETS_DIR = Path("orca/assets")
JURISDICTIONS_FILE = ASSETS_DIR / "jurisdictions.json"
DEFAULT_OUTPUT = ASSETS_DIR / "jurisdictions_report.html"
GENERATE_SCRIPT = Path("orca/scripts/generate_jurisdictions_report.py")


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
    async with streamablehttp_client(url=config["url"], headers=config.get("headers", {})) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


async def fetch_jurisdictions(config):
    print("Fetching jurisdictions...")
    async for session in get_mcp_session(config):
        result = await session.call_tool("list_jurisdictions", {"limit": 2**31 - 1})
        content = _parse_content(result)
        jurisdictions = content.get("jurisdictions", [])
        print(f"Fetched {len(jurisdictions)} jurisdictions")
        return jurisdictions


async def main():
    parser = argparse.ArgumentParser(description="Fetch jurisdictions and generate report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file path")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path} (URL: {config.get('url')})")

    jurisdictions = await fetch_jurisdictions(config)
    if not jurisdictions:
        print("No jurisdictions returned.")
        raise SystemExit(1)

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"jurisdictions": jurisdictions}
    JURISDICTIONS_FILE.write_text(json.dumps(payload, indent=2))
    print(f"Saved {len(jurisdictions)} jurisdictions to {JURISDICTIONS_FILE}")

    print(f"\nGenerating report...")
    result = subprocess.run(
        [sys.executable, str(GENERATE_SCRIPT), str(JURISDICTIONS_FILE), Path(args.output).name],
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"Report generation failed (exit code {result.returncode})")
        raise SystemExit(result.returncode)

    print(f"\nDone. Report saved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
