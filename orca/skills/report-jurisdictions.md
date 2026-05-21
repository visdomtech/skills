# Jurisdictions Report Generation

## Overview

This skill describes how to generate a comprehensive HTML report from Orca jurisdictions data. The report includes counts by jurisdiction level (federal, state, city) and identifies invalid, useless, or meaningless jurisdiction entries.

All MCP communication is handled via `scripts/common/tools/mcp_wrapper_base.py`.

## Prerequisites

- Access to the Orca MCP server
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)
- MCP config JSON (see Step 1)

## Pipeline

### Step 1: Prepare Environment and Run Script

Set up the Python environment and run the fetch script, which calls `list_jurisdictions` via the MCP SDK and generates the report automatically.

```bash
# Prepare virtual environment
cd orca
uv sync

# Run fetch + report generation
uv run report-jurisdictions-fetch --config assets/mcp_config.json

# Optional: specify a custom output path
uv run report-jurisdictions-fetch --config assets/mcp_config.json --output assets/my_report.html
```

The script:
1. Connects to the Orca MCP server via the MCP SDK
2. Calls `list_jurisdictions` to retrieve all jurisdictions
3. Saves the raw data to `assets/jurisdictions.json`
4. Runs `generate_jurisdictions_report.py` to produce the HTML report

**MCP config format** (`assets/mcp_config.json`):
```json
{
  "type": "http",
  "url": "https://orcaservices-360095844563.us-central1.run.app",
  "headers": {
    "X-API-KEY": "your-api-key-here"
  }
}
```

## Step 2: Analyze the Data

### 2.1 Count by Jurisdiction Level

Group and count jurisdictions by the `jurisdiction_type` field. The expected types are:

- `FEDERAL` — Typically 1 (United States)
- `STATE` — US states and territories
- `CITY` — Municipal jurisdictions

Example counts from a typical dataset:

| Level  | Count |
|--------|-------|
| FEDERAL| 1     |
| STATE  | 52    |
| CITY   | 304   |
| **Total** | **357** |

### 2.2 Identify Invalid / Useless / Meaningless Jurisdictions

Scan every jurisdiction entry and flag those matching any of the following criteria:

#### Criterion A: Code-like Names

A jurisdiction whose `name` field is literally a code pattern instead of a human-readable place name.

**Pattern:** `^US-[A-Z]{2}-[A-Z0-9]+$`

**Examples of bad entries:**
- `name`: `US-AL-BIR`, `code`: `US-AL-BIR`
- `name`: `US-CT-HFD`, `code`: `US-CT-HFD`
- `name`: `US-IA-CR`, `code`: `US-IA-CR`

These are data-quality failures: the `name` field should contain the actual city name (e.g., "Birmingham", "Hartford", "Cedar Rapids"), not the machine code.

#### Criterion B: Non-Jurisdiction Titles

A jurisdiction whose `name` appears to be a legal document or regulation title rather than a place name.

**Patterns to detect:**
- Contains the phrase `codified laws` (case-insensitive)
- Contains the word `title ` followed by a number (case-insensitive)

**Example of bad entry:**
- `name`: `South Dakota Codified Laws Title 60 - Labor and Employment`
- `type`: `STATE`

This is clearly a regulation title mistakenly stored as a state jurisdiction.

#### Criterion C: Missing Parent Jurisdiction

Any non-federal jurisdiction with `parent_jurisdiction_id` equal to `null`.

**Rules:**
- `FEDERAL` entries may have `null` parent (the root).
- `STATE` entries should have parent `1` (United States).
- `CITY` entries should have a state as their parent.

#### Criterion D: Empty or Very Short Names

A jurisdiction whose `name` field is empty, null, or fewer than 2 characters after trimming.

#### Criterion E: Abbreviation as City Name

A `CITY` entry whose `name` is all uppercase, 5 characters or fewer, and looks like an abbreviation rather than a full city name.

**Example:** `name`: `CR` instead of `Cedar Rapids`.

### 2.3 Collect Reasons for Each Flagged Entry

For every flagged jurisdiction, build a list of human-readable reasons. A single jurisdiction may match multiple criteria.

Common reason strings:
- `name is a code pattern instead of a place name`
- `name appears to be a legal document title, not a jurisdiction`
- `missing parent jurisdiction`
- `name too short or empty`
- `name is an abbreviation, not a full city name`

## Step 3: Generate the HTML Report

### 3.1 Design Principles for Gmail Compatibility

Use table-based layouts with **inline CSS** only. Gmail strips `<style>` tags and external stylesheets, so every visual rule must be inline.

Key guidelines:
- Use `<table role="presentation">` for layout containers.
- Use `cellspacing="0" cellpadding="0" border="0"` on tables.
- Use `style="border-collapse:collapse;"` for data tables.
- Nest a fixed-width inner table (e.g., `width="700"` or `max-width:700px`) inside a `width="100%"` outer table to center content.
- Avoid `div`-based layouts; they break in many email clients.

### 3.2 Professional Color Palette

Use a refined slate/navy palette instead of basic primary colors:

| Role | Color |
|------|-------|
| Background | `#f1f5f9` (light slate) |
| Card background | `#ffffff` |
| Primary text (navy) | `#1e293b` |
| Secondary text (slate) | `#475569` |
| Muted text | `#64748b` |
| Borders | `#e2e8f0` |
| Federal badge | `#eff6ff` bg / `#1d4ed8` text |
| State badge | `#f0fdf4` bg / `#15803d` text |
| City badge | `#fff7ed` bg / `#c2410c` text |

### 3.3 Report Sections

#### Hero Header

A dark navy (`#1e293b`) header bar spanning the full width of the card with rounded top corners.

- Left side: Large title (`font-size:28px; font-weight:700; color:#ffffff`) and subtitle (`color:#94a3b8`)
- Right side: Generation date in uppercase with letter-spacing (`letter-spacing:1px`)

#### Data Health Score

A prominent metrics bar below the header showing the overall data quality:

- Left: "Data Health Score" label (uppercase, `letter-spacing:1.2px`) with descriptive text
- Right: Large percentage score (`font-size:36px; font-weight:800; color:#1e293b`)
- Below: Two-segment progress bar
  - Green segment (`#15803d`) representing valid percentage
  - Red segment (`#dc2626`) representing flagged percentage

Calculate: `health_pct = round((total - flagged) / total * 100)`

#### Distribution Cards

Three side-by-side cards with subtle colored borders and backgrounds:

1. **Federal** — Blue theme (`#eff6ff` background, `#dbeafe` border, `#1d4ed8` text)
2. **State** — Green theme (`#f0fdf4` background, `#bbf7d0` border, `#15803d` text)
3. **City** — Orange theme (`#fff7ed` background, `#fed7aa` border, `#c2410c` text)

Each card shows:
- Extra-large numeric count (`font-size:36px; font-weight:800; letter-spacing:-1px`)
- Level label in uppercase (`font-weight:700; letter-spacing:1.2px`)
- Descriptive sub-label (e.g., "National Level", "Territory Level", "Municipal Level")

Follow the cards with a total count bar in `#f8fafc` with left/right split layout.

#### Invalid Jurisdictions Table

A full-width table with rounded corners (`border-radius:10px; overflow:hidden`) and a subtle outer border.

| Column | Description |
|--------|-------------|
| ID | `jurisdiction_id` in monospace font |
| Type | Pill badge styled by level with border |
| Name | The `name` field, bolded (`font-weight:600`) |
| Code | The `code` field in monospace font |
| Issues | Color-coded pill badges for each reason |

**Type badge style (pill with border):**
```html
<span style="display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.8px;background-color:#eff6ff;color:#1d4ed8;border:1px solid #dbeafe;">Federal</span>
```

**Issue tag styles (color-coded by severity):**

| Issue Type | Background | Text | Border |
|------------|------------|------|--------|
| Code pattern | `#fff7ed` | `#c2410c` | `#fed7aa` |
| Legal document | `#fef3c7` | `#b45309` | `#fde68a` |
| Missing parent | `#eff6ff` | `#1d4ed8` | `#dbeafe` |
| Other | `#fef2f2` | `#dc2626` | `#fecaca` |

Base pill style:
```html
<span style="display:inline-block;padding:4px 10px;border-radius:20px;font-size:11px;font-weight:600;margin:3px 3px 3px 0;white-space:nowrap;">REASON_TEXT</span>
```

Render **one span per reason** so multiple issues on the same row appear as separate inline tags that wrap naturally.

**Table row styling:**
- Alternate row backgrounds (`#ffffff` / `#f8fafc`).
- Bottom border on every cell (`border-bottom:1px solid #e2e8f0`).
- Header row with `#f8fafc` background and thicker bottom border (`border-bottom:2px solid #e2e8f0`).
- Generous cell padding (`padding:14px 16px`).

#### Issue Legend

A dedicated legend section below the table explaining the color coding:

- Container: `#f8fafc` background with rounded corners and border
- Label: "Issue Legend" in uppercase
- Inline row of sample tags showing each color category

#### Footer

A centered footer with:
- Primary line: Report name and generator (`font-weight:500`)
- Secondary line: Confidentiality notice (`font-size:11px; color:#94a3b8`)

Example:
```
Orca Jurisdictions Data Quality Report · Generated by Orca MCP
Confidential — For internal use only
```

### 3.4 Complete HTML Structure Outline

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Orca Jurisdictions Report</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:...">
  <!-- Outer full-width table -->
  <table role="presentation" width="100%" ...>
    <tr>
      <td align="center" style="padding:48px 16px;">
        <!-- Inner content card (max-width:700px) -->
        <table role="presentation" width="700" ...>
          <!-- Hero Header row -->
          <!-- Health Score row -->
          <!-- Summary cards row -->
          <!-- Totals bar row -->
          <!-- Divider row -->
          <!-- Invalid table row -->
          <!-- Issue Legend row -->
          <!-- Footer row -->
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

## Step 4: Save and Deliver

Save the generated HTML to a file in the workspace. The report is now ready to:

- Be opened in a web browser for preview.
- Be copied and pasted into a Gmail compose window (the inline styles and table layout ensure it renders correctly).
- Be sent via email — **follow `orca/skills/send-email.md`** for the correct workflow. Use `--html` to send the report as the email body, or `--attach` to send it as a file attachment (or both).

## Automated Scripts

### `fetch_jurisdictions.py` (MCP SDK — primary entry point)

Fetches jurisdictions from the Orca MCP server and generates the HTML report in one command.

```bash
uv run report-jurisdictions-fetch --config assets/mcp_config.json [--output <path>]
```

Saves raw data to `assets/jurisdictions.json`, then invokes `generate_jurisdictions_report.py` automatically.

### `generate_jurisdictions_report.py` (analysis + HTML generation)

Can also be run standalone on previously fetched data:

```bash
uv run python3 scripts/report_jurisdictions/generate_jurisdictions_report.py <path_to_jurisdictions_json> [output_file]
```

**Parameters:**
- `path_to_jurisdictions_json` (required): Path to a JSON file with a `jurisdictions` array.
- `output_file` (optional): Output HTML file path. Defaults to `jurisdictions_report.html`.

The script handles all analysis logic — counting by level, detecting invalid entries via the five criteria (A–E), computing the data health score, and generating the full Gmail-compatible HTML report with inline styles.

## Example Output Summary

A typical report will show:

- **Total jurisdictions:** 357
- **Federal:** 1
- **State:** 52
- **City:** 304
- **Flagged entries:** ~84 (mostly cities with code-like names and missing parent references, plus one misclassified state)

## Key Takeaways

1. Always parse the raw `list_jurisdictions` JSON programmatically; do not rely on manual inspection of large responses.
2. Use regex (`^US-[A-Z]{2}-[A-Z0-9]+$`) to detect the most common data-quality failure: code-like names.
3. Always check `parent_jurisdiction_id` for hierarchy integrity.
4. Use inline CSS and table-based layout for email-safe HTML.
5. Render each issue reason as a separate inline tag badge in the Issues column for visual clarity.
