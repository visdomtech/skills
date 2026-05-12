#!/usr/bin/env python3
"""Generate RAG metadata report using MCP SDK.

Fetches metadata for all documents in the compliance repository and generates:
1. A detailed CSV report of all metadata entries.
2. An HTML summary report focusing on jurisdiction_code distribution and missing metadata.
"""

import argparse
import asyncio
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


# Configuration
WORKSPACE_ID = 1
REPOSITORY_ID = 6
DOCUMENTS_FILE = Path("orca/assets/compliance_documents.json")
CSV_OUTPUT = Path("orca/assets/rag_metadata_report.csv")
HTML_OUTPUT = Path("orca/assets/rag_metadata_summary.html")
CONCURRENCY_LIMIT = 5


def load_documents():
    """Load documents from the cached JSON file."""
    if not DOCUMENTS_FILE.exists():
        print(f"Error: Documents file not found at {DOCUMENTS_FILE}")
        raise SystemExit(1)
    
    with open(DOCUMENTS_FILE, "r") as f:
        data = json.load(f)
    
    # Handle cache wrapper format
    if "response" in data and "data" in data["response"]:
        return data["response"]["data"].get("documents", [])
    return data.get("documents", [])


async def get_mcp_session(config):
    """Yield an initialized MCP session via HTTP/SSE."""
    if config.get("type") != "http":
        raise ValueError(f"Unsupported transport: {config['type']}")
    async with streamablehttp_client(url=config["url"], headers=config.get("headers", {})) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


def _parse_content(result):
    """Parse MCP tool result content into a dictionary."""
    if not result.content:
        return {}
    
    if isinstance(result.content, list):
        for item in result.content:
            if hasattr(item, 'text'):
                try:
                    return json.loads(item.text)
                except json.JSONDecodeError:
                    continue
            elif isinstance(item, dict):
                return item
    
    if isinstance(result.content, dict):
        return result.content
    
    if hasattr(result.content, 'text'):
        try:
            return json.loads(result.content.text)
        except json.JSONDecodeError:
            return {}
            
    return {}


async def fetch_metadata(session, doc, semaphore):
    """Fetch metadata for a single document with concurrency control."""
    rag_name = doc.get("rag_file_name")
    filename = doc.get("filename", "Unknown")
    
    if not rag_name:
        return {
            "filename": filename,
            "rag_file_name": "",
            "metadata": [],
            "error": "No rag_file_name"
        }

    async with semaphore:
        try:
            result = await session.call_tool("list_rag_metadata", {"ragFileName": rag_name})
            content = _parse_content(result)
            metadata = content.get("metadata", [])
            return {
                "filename": filename,
                "rag_file_name": rag_name,
                "metadata": metadata,
                "error": None
            }
        except Exception as e:
            print(f"  Warning: Failed to fetch metadata for {filename}: {e}")
            return {
                "filename": filename,
                "rag_file_name": rag_name,
                "metadata": [],
                "error": str(e)
            }


def generate_csv(results):
    """Write detailed metadata to CSV."""
    rows = []
    for res in results:
        if res["error"] and res["error"] != "No rag_file_name":
            rows.append({
                "filename": res["filename"],
                "rag_file_name": res["rag_file_name"],
                "metadata_key": "ERROR",
                "metadata_value": res["error"]
            })
        elif not res["metadata"]:
            rows.append({
                "filename": res["filename"],
                "rag_file_name": res["rag_file_name"],
                "metadata_key": "",
                "metadata_value": ""
            })
        else:
            for entry in res["metadata"]:
                rows.append({
                    "filename": res["filename"],
                    "rag_file_name": res["rag_file_name"],
                    "metadata_key": entry.get("key", ""),
                    "metadata_value": entry.get("value", "")
                })
    
    with open(CSV_OUTPUT, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "rag_file_name", "metadata_key", "metadata_value"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Detailed CSV written to {CSV_OUTPUT} ({len(rows)} rows)")


def generate_html(results):
    """Generate summary HTML report."""
    total_docs = len(results)
    docs_with_jurisdiction = 0
    jurisdiction_counts = {}
    missing_jurisdiction = []

    for res in results:
        has_jurisdiction = False
        metadata_list = res.get("metadata") or []
        for entry in metadata_list:
            if entry.get("key") == "jurisdiction_code":
                val = entry.get("value", "Unknown")
                jurisdiction_counts[val] = jurisdiction_counts.get(val, 0) + 1
                has_jurisdiction = True
                break
        
        if has_jurisdiction:
            docs_with_jurisdiction += 1
        else:
            missing_jurisdiction.append(res["filename"])

    docs_without_jurisdiction = total_docs - docs_with_jurisdiction

    # Sort jurisdiction counts by count descending
    sorted_jurisdictions = sorted(jurisdiction_counts.items(), key=lambda x: x[1], reverse=True)

    now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    # Helper for table rows
    def render_jurisdiction_rows(items):
        rows = ""
        for i, (code, count) in enumerate(items):
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            rows += f"""
            <tr>
                <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-weight:600;color:#1e293b;">{code}</td>
                <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};color:#475569;text-align:center;">{count}</td>
            </tr>"""
        return rows

    def render_missing_rows(items):
        rows = ""
        limit = 100 if len(items) > 100 else len(items)
        for i in range(limit):
            bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
            rows += f"""
            <tr>
                <td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};color:#475569;">{items[i]}</td>
            </tr>"""
        if len(items) > 100:
            rows += f"""
            <tr>
                <td style="padding:12px 16px;background-color:#f8fafc;text-align:center;color:#64748b;font-style:italic;">... {len(items) - 100} more ...</td>
            </tr>"""
        return rows

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RAG Jurisdiction Metadata Summary</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
    <tr>
      <td align="center" style="padding:48px 16px;">
        <table role="presentation" width="700" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;">

          <!-- Hero Header -->
          <tr>
            <td style="background-color:#1e293b;padding:40px 48px;">
              <div style="font-size:28px;font-weight:700;color:#ffffff;margin-bottom:6px;">RAG Jurisdiction Metadata Summary</div>
              <div style="font-size:14px;color:#94a3b8;">Orca Platform · Compliance Repository Audit</div>
            </td>
          </tr>

          <!-- Summary Metrics -->
          <tr>
            <td style="padding:36px 48px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="33%">
                    <div style="font-size:36px;font-weight:800;color:#1e293b;">{total_docs}</div>
                    <div style="font-size:11px;color:#64748b;text-transform:uppercase;">Total Documents</div>
                  </td>
                  <td width="33%" align="center">
                    <div style="font-size:36px;font-weight:800;color:#15803d;">{docs_with_jurisdiction}</div>
                    <div style="font-size:11px;color:#64748b;text-transform:uppercase;">With Jurisdiction</div>
                  </td>
                  <td width="33%" align="right">
                    <div style="font-size:36px;font-weight:800;color:#dc2626;">{docs_without_jurisdiction}</div>
                    <div style="font-size:11px;color:#64748b;text-transform:uppercase;">Missing Jurisdiction</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Jurisdiction Distribution -->
          <tr>
            <td style="padding:0 48px 36px;">
              <div style="font-size:18px;font-weight:700;color:#1e293b;margin-bottom:16px;">Jurisdiction Distribution</div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr>
                    <th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Jurisdiction Code</th>
                    <th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:center;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Document Count</th>
                  </tr>
                </thead>
                <tbody>
                  {render_jurisdiction_rows(sorted_jurisdictions)}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Missing Metadata List -->
          <tr>
            <td style="padding:0 48px 36px;">
              <div style="font-size:18px;font-weight:700;color:#1e293b;margin-bottom:16px;">Documents Missing Jurisdiction Metadata</div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
                <tbody>
                  {render_missing_rows(missing_jurisdiction)}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:36px 48px;background-color:#f8fafc;border-top:1px solid #e2e8f0;">
              <div style="font-size:13px;font-weight:500;color:#475569;text-align:center;">Generated on {now}</div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    with open(HTML_OUTPUT, "w") as f:
        f.write(html)
    
    print(f"Summary HTML written to {HTML_OUTPUT}")


async def main():
    parser = argparse.ArgumentParser(description="Generate RAG metadata report")
    parser.add_argument("--config", required=True, help="Path to MCP config JSON")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Config not found: {config_path}")
        raise SystemExit(1)

    config = json.loads(config_path.read_text())
    print(f"Config loaded from {config_path}")

    documents = load_documents()
    print(f"Loaded {len(documents)} documents")

    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    results = []

    async for session in get_mcp_session(config):
        tasks = [fetch_metadata(session, doc, semaphore) for doc in documents]
        
        # Use gather with return_exceptions to handle errors gracefully without crashing the task group
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, res in enumerate(raw_results):
            if isinstance(res, Exception):
                print(f"  Warning: Task {i} failed: {res}")
                results.append({
                    "filename": documents[i].get("filename", "Unknown"),
                    "rag_file_name": documents[i].get("rag_file_name", ""),
                    "metadata": [],
                    "error": str(res)
                })
            else:
                results.append(res)
            
            if (i + 1) % 50 == 0:
                print(f"Processed {i + 1}/{len(documents)} documents...")

    generate_csv(results)
    generate_html(results)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
