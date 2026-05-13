#!/usr/bin/env python3
"""Send an email via the Orca MCP send_email tool, with optional file attachments.

Usage:
    uv run send-email \\
        --config assets/mcp_config.json \\
        --to recipient@example.com \\
        --subject "My Subject" \\
        --text "Body text" \\
        [--html path/to/body.html] \\
        [--attach path/to/file.pdf] \\
        [--attach path/to/report.html] \\
        [--from sender@doublefin.ai] \\
        [--cc cc@example.com] \\
        [--bcc bcc@example.com]

The script base64-encodes each attachment and invokes the Orca MCP send_email tool
directly using the MCP Python SDK.

Exit codes:
    0  success
    1  missing required arguments or file not found
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import mimetypes
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


ASSETS_DIR = Path("assets")
DEFAULT_CONFIG = ASSETS_DIR / "mcp_config.json"


def encode_attachment(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"Error: attachment not found: {path}", file=sys.stderr)
        sys.exit(1)
    mime, _ = mimetypes.guess_type(str(p))
    if mime is None:
        mime = "application/octet-stream"
    data = base64.b64encode(p.read_bytes()).decode("ascii")
    return {"filename": p.name, "contentType": mime, "data": data}


def build_payload(args: argparse.Namespace) -> dict:
    payload: dict = {
        "from": args.from_addr,
        "to": args.to,
        "subject": args.subject,
    }
    if args.cc:
        payload["cc"] = args.cc
    if args.bcc:
        payload["bcc"] = args.bcc
    if args.text:
        payload["text"] = args.text
    if args.html:
        html_path = Path(args.html)
        if not html_path.exists():
            print(f"Error: HTML body file not found: {args.html}", file=sys.stderr)
            sys.exit(1)
        payload["html"] = html_path.read_text(encoding="utf-8")
    if args.attach:
        payload["attachments"] = [encode_attachment(a) for a in args.attach]
    return payload


@asynccontextmanager
async def get_mcp_session(config):
    """Yield an initialized MCP session via HTTP/SSE."""
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    client = httpx.AsyncClient(headers=config.get("headers", {}))
    async with client:
        async with streamable_http_client(url=config["url"], http_client=client) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session


async def send_email_async(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(config_path.read_text())
    payload = build_payload(args)

    print(f"Sending email to {', '.join(args.to)}...")
    async with get_mcp_session(config) as session:
        result = await session.call_tool("send_email", payload)
        # Check for errors in the result
        if hasattr(result, 'isError') and result.isError:
            print(f"Error sending email: {result.content}", file=sys.stderr)
            sys.exit(1)
        print("Email sent successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send email via Orca MCP, with optional file attachments."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to MCP config JSON")
    parser.add_argument("--to", nargs="+", required=True, metavar="EMAIL",
                        help="Recipient address(es)")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--from", dest="from_addr", default="support@doublefin.com",
                        metavar="EMAIL", help="Sender address")
    parser.add_argument("--text", help="Plain-text body")
    parser.add_argument("--html", metavar="FILE",
                        help="Path to an HTML file to use as the email body")
    parser.add_argument("--attach", nargs="+", metavar="FILE",
                        help="Path(s) to file(s) to attach")
    parser.add_argument("--cc", nargs="+", metavar="EMAIL", help="CC address(es)")
    parser.add_argument("--bcc", nargs="+", metavar="EMAIL", help="BCC address(es)")
    args = parser.parse_args()

    if not args.text and not args.html:
        parser.error("At least one of --text or --html is required.")

    asyncio.run(send_email_async(args))


if __name__ == "__main__":
    main()
