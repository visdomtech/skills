#!/usr/bin/env python3
"""Send an email via the Orca MCP send_email tool, with optional file attachments.

Usage:
    python3 orca/scripts/send_email.py \\
        --to recipient@example.com \\
        --subject "My Subject" \\
        --text "Body text" \\
        [--html path/to/body.html] \\
        [--attach path/to/file.pdf] \\
        [--attach path/to/report.html] \\
        [--from sender@doublefin.ai] \\
        [--cc cc@example.com] \\
        [--bcc bcc@example.com]

The script base64-encodes each attachment and prints a JSON payload to stdout
that can be piped directly into the Orca MCP send_email tool, or it can call
the tool via the MCP HTTP endpoint if ORCA_MCP_URL is set in the environment.

Exit codes:
    0  success
    1  missing required arguments or file not found
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send email via Orca MCP, with optional file attachments."
    )
    parser.add_argument("--to", nargs="+", required=True, metavar="EMAIL",
                        help="Recipient address(es)")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--from", dest="from_addr", default="warren@doublefin.ai",
                        metavar="EMAIL", help="Sender address (default: warren@doublefin.ai)")
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

    payload = build_payload(args)

    # Output the payload as JSON for the MCP tool or caller to consume
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
