#!/usr/bin/env python3
"""Start an async GCS-to-RAG-corpus import. Non-existent URIs are skipped and reported in nonExist. Returns operationName immediately; poll with get_import_rag_files_result.

Example input CSV:
    corpusName,gcsUris
    ...,...

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

TOOL_NAME = "import_rag_files"



async def main():
    parser = build_argparser(TOOL_NAME, None, "Start an async GCS-to-RAG-corpus import. Non-existent URIs are skipped and reported in nonExist. Returns operationName immediately; poll with get_import_rag_files_result.", "Example input CSV:\n    corpusName,gcsUris\n    ...,...\n\nExample output CSV:\n    result_field1,result_field2,...\n    value1,value2,...\n")
    args = parser.parse_args()

    print(f"Loading input CSV: {args.csv}", flush=True)
    rows = parse_csv_input(args.csv, args.limit)
    print(f"Loaded {len(rows)} rows", flush=True)

    all_rows = []
    async with get_mcp_session(args.config) as session:
        for i, row in enumerate(rows):
            print(f"  Processing row {i+1}/{len(rows)}...", flush=True)
            params = {
            "corpusName": row["corpusName"],
            "gcsUris": json.loads(row["gcsUris"]),
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