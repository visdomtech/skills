#!/usr/bin/env python3
"""Generate document-to-RAG-file matching report from Orca list_documents and list_rag_files JSON responses."""

import json, os, sys
from datetime import datetime, timezone

# Paths
DOCS_FILE = sys.argv[1] if len(sys.argv) > 1 else None
RAG_FILES = sys.argv[2] if len(sys.argv) > 2 else None
OUTPUT_FILE = sys.argv[3] if len(sys.argv) > 3 else "document_rag_file_report.html"

if not DOCS_FILE or not RAG_FILES:
    print("Usage: python3 generate_document_rag_file_report.py <path_to_documents_cache> <path_to_rag_files_cache> [output_file]")
    sys.exit(1)

# Load data
def load_json(path):
    with open(path, "r") as f:
        raw = json.load(f)
    
    # If this is a cache file, extract the response data
    if "response" in raw and "data" in raw["response"]:
        return raw["response"]["data"]
    return raw

documents_data = load_json(DOCS_FILE)
rag_files_data = load_json(RAG_FILES)

documents = documents_data.get("documents", [])
rag_files = rag_files_data.get("files", [])

total_docs = len(documents)
total_rag = len(rag_files)

print(f"Loaded {total_docs} documents and {total_rag} RAG files")

# --- Step 2: Analysis ---

# Build RAG lookup map: displayName -> name
rag_map = {}
for rf in rag_files:
    display_name = rf.get("displayName", "")
    rag_name = rf.get("name", "")
    if display_name:
        rag_map[display_name] = rag_name

# Classify documents
unmatched = []
matched_empty = []
matched_correct = []
matched_different = []

for doc in documents:
    filename = doc.get("filename", "")
    if not filename:
        continue
    
    existing_rag = doc.get("rag_file_name")
    
    if filename not in rag_map:
        unmatched.append({
            "document_id": doc.get("document_id"),
            "filename": filename,
            "rag_file_name": existing_rag,
        })
    else:
        matching_rag = rag_map[filename]
        
        if not existing_rag or existing_rag == "":
            matched_empty.append({
                "document_id": doc.get("document_id"),
                "filename": filename,
                "current_rag_file_name": existing_rag,
                "matching_rag_file_name": matching_rag,
            })
        elif existing_rag == matching_rag:
            matched_correct.append({
                "document_id": doc.get("document_id"),
                "filename": filename,
                "rag_file_name": existing_rag,
            })
        else:
            matched_different.append({
                "document_id": doc.get("document_id"),
                "filename": filename,
                "current_rag_file_name": existing_rag,
                "matching_rag_file_name": matching_rag,
            })

unmatched_count = len(unmatched)
empty_count = len(matched_empty)
correct_count = len(matched_correct)
different_count = len(matched_different)
matched_total = empty_count + correct_count + different_count

print(f"Unmatched: {unmatched_count}")
print(f"Matched - Empty/Null: {empty_count}")
print(f"Matched - Correct: {correct_count}")
print(f"Matched - Different: {different_count}")

# --- Step 3: Generate HTML ---

def status_badge(status):
    colors = {
        "Unmatched":      ("#f1f5f9", "#475569", "#e2e8f0"),
        "Empty/Null":     ("#fffbeb", "#b45309", "#fde68a"),
        "Correct":        ("#f0fdf4", "#15803d", "#bbf7d0"),
        "Different":      ("#fef2f2", "#dc2626", "#fecaca"),
    }
    bg, fg, bd = colors.get(status, ("#f8fafc", "#475569", "#e2e8f0"))
    return f'<span style="display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;background-color:{bg};color:{fg};border:1px solid {bd};">{status}</span>'

def truncate(text, max_len=60):
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len] + "..."
    return text

def render_table_rows(items, columns, show_current_rag=True, show_matching_rag=True):
    rows = ""
    for i, item in enumerate(items):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        cols = f'<td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-family:monospace;font-size:13px;color:#475569;">{item["document_id"]}</td>'
        cols += f'<td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-weight:600;color:#1e293b;">{item["filename"]}</td>'
        
        if show_current_rag:
            current = truncate(item.get("current_rag_file_name") or item.get("rag_file_name") or "(none)")
            cols += f'<td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-family:monospace;font-size:12px;color:#64748b;">{current}</td>'
        
        if show_matching_rag:
            matching = truncate(item.get("matching_rag_file_name", ""))
            cols += f'<td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-family:monospace;font-size:12px;color:#64748b;">{matching}</td>'
        
        rows += f"<tr>{cols}</tr>"
    return rows

def render_section(title, items, status_type, show_current_rag=True, show_matching_rag=True):
    count = len(items)
    if count == 0:
        return ""
    
    badge = status_badge(status_type)
    
    # Show first 20 and last 20 if more than 20
    if count > 40:
        display_items = items[:20] + items[-20:]
        middle_note = f'<tr><td colspan="5" style="padding:12px 16px;background-color:#f8fafc;text-align:center;color:#64748b;font-style:italic;">... {count - 40} more entries ...</td></tr>'
    else:
        display_items = items
        middle_note = ""
    
    table_rows = render_table_rows(display_items, [], show_current_rag, show_matching_rag)
    if middle_note:
        # Insert middle note after first 20 rows
        parts = table_rows.split("</tr>")
        if len(parts) > 20:
            first_20 = "</tr>".join(parts[:20]) + "</tr>"
            rest = "</tr>".join(parts[20:])
            table_rows = first_20 + middle_note + rest
    
    header_cols = '<th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">ID</th>'
    header_cols += '<th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Filename</th>'
    if show_current_rag:
        header_cols += '<th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Current rag_file_name</th>'
    if show_matching_rag:
        header_cols += '<th style="padding:12px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Matching RAG File</th>'
    
    return f"""
          <!-- {title} Section -->
          <tr>
            <td style="padding:36px 48px 20px;">
              <div style="font-size:18px;font-weight:700;color:#1e293b;">{title}</div>
              <div style="font-size:13px;color:#64748b;margin-top:4px;">{count} entries {badge}</div>
            </td>
          </tr>
          <tr>
            <td style="padding:0 48px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr>{header_cols}</tr>
                </thead>
                <tbody>{table_rows}
                </tbody>
              </table>
            </td>
          </tr>"""

now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document RAG File Matching Report</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
    <tr>
      <td align="center" style="padding:48px 16px;">
        <table role="presentation" width="700" cellspacing="0" cellpadding="0" border="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;">

          <!-- Hero Header -->
          <tr>
            <td style="background-color:#1e293b;padding:40px 48px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <div style="font-size:28px;font-weight:700;color:#ffffff;margin-bottom:6px;">Document RAG File Matching Report</div>
                    <div style="font-size:14px;color:#94a3b8;">Orca Platform · Document-to-RAG Corpus Audit</div>
                  </td>
                  <td align="right" valign="top">
                    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;white-space:nowrap;">{now}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Summary Metrics Bar -->
          <tr>
            <td style="padding:36px 48px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px;">Summary</div>
                    <div style="font-size:14px;color:#475569;">{total_docs} total documents · {total_rag} RAG files in corpus</div>
                  </td>
                  <td align="right" width="120">
                    <div style="font-size:36px;font-weight:800;color:#1e293b;">{matched_total}</div>
                    <div style="font-size:11px;color:#64748b;">matched</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Status Distribution Cards -->
          <tr>
            <td style="padding:0 48px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="25%" style="padding-right:8px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f1f5f9;border:1px solid #e2e8f0;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#475569;">{unmatched_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">Unmatched</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">No RAG match</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="25%" style="padding:0 4px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#fffbeb;border:1px solid #fde68a;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#b45309;">{empty_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#b45309;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">Empty/Null</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">Needs update</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="25%" style="padding:0 4px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#15803d;">{correct_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#15803d;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">Correct</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">Already set</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="25%" style="padding-left:8px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#fef2f2;border:1px solid #fecaca;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#dc2626;">{different_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#dc2626;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">Different</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">Needs fix</div>
                      </td></tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Divider -->
          <tr>
            <td style="padding:0 48px;">
              <div style="border-top:1px solid #e2e8f0;"></div>
            </td>
          </tr>

          <!-- Unmatched Section -->
          {render_section("Unmatched Documents", unmatched, "Unmatched", show_current_rag=False, show_matching_rag=False)}

          <!-- Matched - Empty/Null Section -->
          {render_section("Documents Needing rag_file_name (Empty/Null)", matched_empty, "Empty/Null")}

          <!-- Matched - Correct Section -->
          {render_section("Documents with Correct rag_file_name", matched_correct, "Correct", show_matching_rag=False)}

          <!-- Matched - Different Section -->
          {render_section("Documents with Incorrect rag_file_name", matched_different, "Different")}

          <!-- Status Legend -->
          <tr>
            <td style="padding:0 48px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">Status Legend</div>
                    {status_badge("Unmatched")}
                    {status_badge("Empty/Null")}
                    {status_badge("Correct")}
                    {status_badge("Different")}
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:36px 48px;background-color:#f8fafc;border-top:1px solid #e2e8f0;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td align="center">
                    <div style="font-size:13px;font-weight:500;color:#475569;">Orca Document RAG File Matching Report &middot; Generated by Orca MCP</div>
                    <div style="font-size:11px;color:#94a3b8;margin-top:4px;">Confidential &mdash; For internal use only</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

with open(OUTPUT_FILE, "w") as f:
    f.write(html)

print(f"\nReport written to {OUTPUT_FILE}")
print(f"Done.")
