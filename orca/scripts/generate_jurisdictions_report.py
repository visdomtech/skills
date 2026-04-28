#!/usr/bin/env python3
"""Generate jurisdictions report from Orca list_jurisdictions JSON response."""

import json, re, os, sys
from datetime import datetime, timezone

# Paths
DATA_FILE = sys.argv[1] if len(sys.argv) > 1 else "cache/orca_cache_0dae01819f04613c.json"
OUTPUT_FILE = sys.argv[2] if len(sys.argv) > 2 else "jurisdictions_report.html"

# Load data
with open(DATA_FILE, "r") as f:
    raw = json.load(f)

# If this is a cache file, extract the response data
if "response" in raw and "data" in raw["response"]:
    jurisdictions = raw["response"]["data"]["jurisdictions"]
else:
    jurisdictions = raw["jurisdictions"]

total = len(jurisdictions)
print(f"Loaded {total} jurisdictions")

# --- Step 2: Analysis ---

# Count by type
type_counts = {}
for j in jurisdictions:
    t = j["jurisdiction_type"]
    type_counts[t] = type_counts.get(t, 0) + 1

federal_count = type_counts.get("FEDERAL", 0)
state_count = type_counts.get("STATE", 0)
city_count = type_counts.get("CITY", 0)

print(f"Federal: {federal_count}, State: {state_count}, City: {city_count}")

# Identify flagged entries
flagged = []
code_pattern = re.compile(r"^US-[A-Z]{2}-[A-Z0-9]+$")

for j in jurisdictions:
    reasons = []
    name = (j.get("name") or "").strip()
    jtype = j.get("jurisdiction_type", "")
    code = (j.get("code") or "").strip()
    parent = j.get("parent_jurisdiction_id")

    # Criterion A: Code-like names
    if code_pattern.match(name):
        reasons.append("name is a code pattern instead of a place name")

    # Criterion B: Non-jurisdiction titles
    if re.search(r"codified laws", name, re.IGNORECASE):
        reasons.append("name appears to be a legal document title, not a jurisdiction")
    elif re.search(r"title \d", name, re.IGNORECASE):
        reasons.append("name appears to be a legal document title, not a jurisdiction")

    # Criterion C: Missing parent jurisdiction
    if jtype != "FEDERAL" and parent is None:
        reasons.append("missing parent jurisdiction")

    # Criterion D: Empty or very short names
    if len(name) < 2:
        reasons.append("name too short or empty")

    # Criterion E: Abbreviation as city name
    if jtype == "CITY" and name == name.upper() and len(name) <= 5 and not name.startswith("US-"):
        # Check it's not a real short city name (like "Reno", "Nome", "Orem")
        # Only flag if it looks like an abbreviation (no vowels or all consonants)
        if re.match(r"^[A-Z]{2,5}$", name):
            reasons.append("name is an abbreviation, not a full city name")

    if reasons:
        flagged.append({
            "jurisdiction_id": j["jurisdiction_id"],
            "type": jtype,
            "name": name,
            "code": code,
            "reasons": reasons,
        })

flagged_count = len(flagged)
health_pct = round((total - flagged_count) / total * 100) if total > 0 else 100
print(f"Flagged: {flagged_count}, Health: {health_pct}%")

# --- Step 3: Generate HTML ---

# Issue tag colors
issue_colors = {
    "code pattern":       {"bg": "#fff7ed", "fg": "#c2410c", "border": "#fed7aa"},
    "legal document":     {"bg": "#fef3c7", "fg": "#b45309", "border": "#fde68a"},
    "missing parent":     {"bg": "#eff6ff", "fg": "#1d4ed8", "border": "#dbeafe"},
    "short":              {"bg": "#fef2f2", "fg": "#dc2626", "border": "#fecaca"},
    "abbreviation":       {"bg": "#fff7ed", "fg": "#c2410c", "border": "#fed7aa"},
}

def issue_tag_class(reason):
    if "code pattern" in reason:
        return "code pattern"
    elif "legal document" in reason:
        return "legal document"
    elif "missing parent" in reason:
        return "missing parent"
    elif "short" in reason:
        return "short"
    elif "abbreviation" in reason:
        return "abbreviation"
    return "short"

def issue_tag_html(reason):
    cat = issue_tag_class(reason)
    c = issue_colors[cat]
    return f'<span style="display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px 3px 3px 0;white-space:nowrap;background-color:{c["bg"]};color:{c["fg"]};border:1px solid {c["border"]};">{reason}</span>'

def type_badge(jtype):
    colors = {
        "FEDERAL": ("#eff6ff", "#1d4ed8", "#dbeafe"),
        "STATE":   ("#f0fdf4", "#15803d", "#bbf7d0"),
        "CITY":    ("#fff7ed", "#c2410c", "#fed7aa"),
    }
    bg, fg, bd = colors.get(jtype, ("#f8fafc", "#475569", "#e2e8f0"))
    label = jtype.capitalize()
    return f'<span style="display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;background-color:{bg};color:{fg};border:1px solid {bd};">{label}</span>'

now = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

flagged_rows = ""
for i, f in enumerate(flagged):
    bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
    tags = "".join(issue_tag_html(r) for r in f["reasons"])
    flagged_rows += f"""
            <tr>
              <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-family:monospace;font-size:13px;color:#475569;">{f["jurisdiction_id"]}</td>
              <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};">{type_badge(f["type"])}</td>
              <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-weight:600;color:#1e293b;">{f["name"]}</td>
              <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};font-family:monospace;font-size:13px;color:#64748b;">{f["code"]}</td>
              <td style="padding:14px 16px;border-bottom:1px solid #e2e8f0;background-color:{bg};">{tags}</td>
            </tr>"""

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Orca Jurisdictions Report</title>
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
                    <div style="font-size:28px;font-weight:700;color:#ffffff;margin-bottom:6px;">Jurisdictions Data Quality Report</div>
                    <div style="font-size:14px;color:#94a3b8;">Orca Platform · Complete Jurisdiction Audit</div>
                  </td>
                  <td align="right" valign="top">
                    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:1px;white-space:nowrap;">{now}</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Data Health Score -->
          <tr>
            <td style="padding:36px 48px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td>
                    <div style="font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:1.2px;margin-bottom:4px;">Data Health Score</div>
                    <div style="font-size:14px;color:#475569;">{total} total jurisdictions · {flagged_count} flagged · {total - flagged_count} clean</div>
                  </td>
                  <td align="right" width="120">
                    <div style="font-size:36px;font-weight:800;color:#1e293b;">{health_pct}%</div>
                  </td>
                </tr>
              </table>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;">
                <tr>
                  <td width="{health_pct}%" style="background-color:#15803d;height:8px;border-radius:4px 0 0 4px;"></td>
                  <td width="{100 - health_pct}%" style="background-color:#dc2626;height:8px;border-radius:0 4px 4px 0;"></td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Distribution Cards -->
          <tr>
            <td style="padding:0 48px 28px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="33%" style="padding-right:10px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#eff6ff;border:1px solid #dbeafe;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#1d4ed8;">{federal_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#1d4ed8;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">Federal</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">National Level</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="33%" style="padding:0 5px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#15803d;">{state_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#15803d;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">State</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">Territory Level</div>
                      </td></tr>
                    </table>
                  </td>
                  <td width="33%" style="padding-left:10px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#fff7ed;border:1px solid #fed7aa;border-radius:10px;">
                      <tr><td style="padding:24px 20px;">
                        <div style="font-size:36px;font-weight:800;letter-spacing:-1px;color:#c2410c;">{city_count}</div>
                        <div style="font-size:11px;font-weight:700;color:#c2410c;text-transform:uppercase;letter-spacing:1.2px;margin-top:4px;">City</div>
                        <div style="font-size:12px;color:#64748b;margin-top:2px;">Municipal Level</div>
                      </td></tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Total Bar -->
          <tr>
            <td style="padding:0 48px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
                <tr>
                  <td style="padding:16px 24px;">
                    <span style="font-size:14px;font-weight:500;color:#475569;">Total Jurisdictions</span>
                  </td>
                  <td align="right" style="padding:16px 24px;">
                    <span style="font-size:18px;font-weight:700;color:#1e293b;">{total}</span>
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

          <!-- Section Header -->
          <tr>
            <td style="padding:36px 48px 20px;">
              <div style="font-size:18px;font-weight:700;color:#1e293b;">Flagged Jurisdictions</div>
              <div style="font-size:13px;color:#64748b;margin-top:4px;">{flagged_count} entries matched one or more data quality criteria</div>
            </td>
          </tr>

          <!-- Invalid Jurisdictions Table -->
          <tr>
            <td style="padding:0 48px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr>
                    <th style="padding:14px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">ID</th>
                    <th style="padding:14px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Type</th>
                    <th style="padding:14px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Name</th>
                    <th style="padding:14px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Code</th>
                    <th style="padding:14px 16px;background-color:#f8fafc;border-bottom:2px solid #e2e8f0;text-align:left;font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.8px;">Issues</th>
                  </tr>
                </thead>
                <tbody>{flagged_rows}
                </tbody>
              </table>
            </td>
          </tr>

          <!-- Issue Legend -->
          <tr>
            <td style="padding:0 48px 36px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
                <tr>
                  <td style="padding:20px 24px;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">Issue Legend</div>
                    {issue_tag_html("name is a code pattern instead of a place name")}
                    {issue_tag_html("name appears to be a legal document title, not a jurisdiction")}
                    {issue_tag_html("missing parent jurisdiction")}
                    {issue_tag_html("name too short or empty")}
                    {issue_tag_html("name is an abbreviation, not a full city name")}
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
                    <div style="font-size:13px;font-weight:500;color:#475569;">Orca Jurisdictions Data Quality Report &middot; Generated by Orca MCP</div>
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

print(f"Report written to {OUTPUT_FILE} ({len(flagged)} flagged entries)")
print(f"Done.")
