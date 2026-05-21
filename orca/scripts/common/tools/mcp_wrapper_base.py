#!/usr/bin/env python3
"""Shared utilities for MCP tool wrapper scripts."""

import argparse
import asyncio
import csv
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@asynccontextmanager
async def get_mcp_session(config_path: str):
    """Yield an initialized MCP session via HTTP/SSE."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    config = json.loads(config_path.read_text())
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config.get('type')}")
    client = httpx.AsyncClient(headers=config.get("headers", {}), timeout=60.0)
    async with client:
        async with streamable_http_client(
            url=config["url"], http_client=client
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


def parse_csv_input(csv_path: str, limit: int | None = None) -> list[dict]:
    """Read a CSV file and return a list of row dictionaries."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {path}")
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            rows.append({k: v for k, v in row.items() if v is not None})
        return rows


def _parse_content(result):
    """Parse MCP tool result content into a Python object."""
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


def flatten_json(obj, prefix: str = "") -> list[dict]:
    """Recursively flatten a JSON response into a list of flat dictionaries.

    - If obj is a list of dicts, returns one flat dict per item.
    - If obj is a dict, returns a single flat dict.
    - If obj is None, returns [{}].
    """
    if obj is None:
        return [{}]
    if isinstance(obj, list):
        if not obj:
            return [{}]
        result = []
        for item in obj:
            result.extend(flatten_json(item, prefix))
        return result
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            new_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                for sub in flatten_json(value, new_key):
                    result.update(sub)
            elif isinstance(value, list):
                result[new_key] = json.dumps(value)
            else:
                result[new_key] = value
        return [result]
    return [{prefix: obj}]


def write_csv_output(rows: list[dict], output_dir: str | Path, tool_name: str) -> Path:
    """Write flattened rows to a CSV file under output_dir/tool_name/.

    Returns the path to the written file.
    """
    output_dir = Path(output_dir)
    tool_dir = output_dir / tool_name
    tool_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = tool_dir / f"result_{timestamp}.csv"

    if not rows:
        output_path.write_text("", encoding="utf-8")
        return output_path

    fieldnames = []
    seen = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return output_path


def _build_example_input(input_schema: dict | None) -> str:
    """Build an example input CSV snippet from the tool's input schema."""
    if not input_schema:
        return "    index\n    1"
    properties = input_schema.get("properties")
    if not properties:
        return "    index\n    1"
    required = set(input_schema.get("required") or [])
    columns = []
    for prop_name in properties:
        if prop_name in required:
            columns.append(prop_name)
        else:
            columns.append(f"{prop_name}?(optional)")
    line = ",".join(columns)
    return f"    {line}\n    " + ",".join(["..." for _ in columns])


def _build_example_output() -> str:
    """Build a generic example output CSV snippet."""
    return "    result_field1,result_field2,...\n    value1,value2,..."


def build_argparser(
    tool_name: str,
    input_schema: dict | None,
    description: str | None = None,
    custom_epilog: str | None = None,
) -> argparse.ArgumentParser:
    """Build an ArgumentParser with --config, --csv, --limit and example CSV help."""
    if custom_epilog:
        epilog = custom_epilog
    else:
        example_input = _build_example_input(input_schema)
        example_output = _build_example_output()

        epilog = f"""Example input CSV:
{example_input}

Example output CSV:
{example_output}
"""

    parser = argparse.ArgumentParser(
        description=description or f"Wrapper for MCP tool: {tool_name}",
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    parser.add_argument("--csv", required=True, help="Path to input CSV")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N rows of the input CSV",
    )
    return parser


async def call_tool_and_parse(session, tool_name: str, params: dict):
    """Call an MCP tool and return the parsed response content."""
    result = await session.call_tool(tool_name, params)
    if result.isError:
        return {"_error": str(result.content)}
    return _parse_content(result)
