#!/usr/bin/env python3
"""Send an email via Mailgun. At least one of text or html must be provided. Attachments are passed as base64-encoded data by the client.

Example input CSV:
    attachments?(optional),bcc?(optional),cc?(optional),from,html?(optional),subject,text?(optional),to
    ...,...,...,...,...,...,...,...

Example output CSV:
    result_field1,result_field2,...
    value1,value2,...
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.common.tools.mcp_wrapper_base import (
    build_argparser,
    call_tool_and_parse,
    flatten_json,
    get_mcp_session,
    parse_csv_input,
    write_csv_output,
)

TOOL_NAME = "send_email"



async def main():
    parser = build_argparser(TOOL_NAME, None, "Send an email via Mailgun. At least one of text or html must be provided. Attachments are passed as base64-encoded data by the client.", "Example input CSV:\n    attachments?(optional),bcc?(optional),cc?(optional),from,html?(optional),subject,text?(optional),to\n    ...,...,...,...,...,...,...,...\n\nExample output CSV:\n    result_field1,result_field2,...\n    value1,value2,...\n")
    args = parser.parse_args()

    print(f"Loading input CSV: {args.csv}", flush=True)
    rows = parse_csv_input(args.csv, args.limit)
    print(f"Loaded {len(rows)} rows", flush=True)

    all_rows = []
    async with get_mcp_session(args.config) as session:
        for i, row in enumerate(rows):
            print(f"  Processing row {i+1}/{len(rows)}...", flush=True)
            params = {
            "attachments": json.loads(row["attachments"]) if row.get("attachments") else None,
            "bcc": json.loads(row["bcc"]) if row.get("bcc") else None,
            "cc": json.loads(row["cc"]) if row.get("cc") else None,
            "from": row["from"],
            "html": row["html"] if row.get("html") else None,
            "subject": row["subject"],
            "text": row["text"] if row.get("text") else None,
            "to": json.loads(row["to"]),
            }
            # Remove None optional values to keep payload clean
            params = {k: v for k, v in params.items() if v is not None}
            response = await call_tool_and_parse(session, TOOL_NAME, params)
            if isinstance(response, dict) and "_error" in response:
                all_rows.append({"_row": i + 1, "_error": response["_error"]})
            else:
                all_rows.extend(flatten_json(response))

    output_path = write_csv_output(all_rows, "cache", TOOL_NAME)
    print(f"Output written to: {output_path}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())