# Send Email

## Overview

Send an email via the Orca MCP `send_email` tool. Supports plain-text and HTML bodies, CC/BCC, and file attachments of any type.

**For emails with file attachments**, always use the helper script `orca/scripts/send_email/send_email.py` — it handles base64-encoding automatically so you never have to encode files manually.

## Prerequisites

- Access to the Orca MCP server (`send_email` tool)
- `uv` for Python environment management (dependencies managed via `orca/pyproject.toml`)

---

## Workflow A — Simple email (no attachments)

Call `mcp__orca__send_email` directly with:

| Field | Required | Notes |
|---|---|---|
| `from` | yes | Sender address |
| `to` | yes | Array of recipient addresses |
| `subject` | yes | Email subject line |
| `text` | one of text/html | Plain-text body |
| `html` | one of text/html | HTML body string |
| `cc` | no | Array of CC addresses |
| `bcc` | no | Array of BCC addresses |

**Example:**

```json
{
  "from": "support@doublefin.com",
  "to": ["recipient@example.com"],
  "subject": "Hello",
  "text": "Body here."
}
```

---

## Workflow B — Email with file attachments

Use `orca/scripts/send_email/send_email.py` to base64-encode the files, then pass the output payload to `mcp__orca__send_email`.

### Step 1: Prepare Environment

Before running the script, ensure your virtual environment is set up and dependencies are installed:

```bash
cd orca
uv sync
```

### Step 2: Generate the payload

Execute the email script using `uv run`:

```bash
# Simple text email with attachment
uv run send-email \
  --to recipient@example.com \
  --subject "Law Changes Report" \
  --text "Please find the report attached." \
  --attach assets/law_changes_report.html

# HTML email body with attachment
uv run send-email \
  --to recipient@example.com \
  --subject "Jurisdictions Report" \
  --html assets/jurisdictions_report.html \
  --attach assets/jurisdictions_report.html
```

### Step 3: Read the base64-encoded attachment data

The script prints a JSON object. Extract the `attachments[0].data` field (the full base64 string) and pass it to `mcp__orca__send_email` as the `data` field of the attachment.

In practice, run the script in Python and capture the output:

```python
import subprocess, json

result = subprocess.run(
    ["uv", "run", "send-email",
     "--to", "recipient@example.com",
     "--subject", "Report",
     "--text", "See attached.",
     "--attach", "assets/law_changes_report.html"],
    capture_output=True, text=True,
    cwd="orca"
)
payload = json.loads(result.stdout)
# payload is now ready to pass to mcp__orca__send_email
```

### Script options

| Flag | Description |
|---|---|
| `--to EMAIL [EMAIL ...]` | Recipient(s) — required |
| `--subject TEXT` | Subject line — required |
| `--from EMAIL` | Sender |
| `--text TEXT` | Plain-text body |
| `--html FILE` | Path to HTML file to use as email body |
| `--attach FILE [FILE ...]` | File(s) to attach (any type; auto-detected MIME) |
| `--cc EMAIL [EMAIL ...]` | CC recipients |
| `--bcc EMAIL [EMAIL ...]` | BCC recipients |

### Sending an HTML file as both body and attachment

```bash
uv run send-email \
  --to recipient@example.com \
  --subject "Law Changes Report" \
  --html assets/law_changes_report.html \
  --attach assets/law_changes_report.html
```

---

## Important notes

1. **Always use the script for attachments** — never manually base64-encode files with shell tools (e.g. `base64 -i`). The script handles encoding correctly; manual encoding leads to truncated or invalid data passed to the MCP tool.
2. **HTML email body vs. attachment:** If the file is an HTML email template (like a law changes report), prefer sending it as the `html` body (`--html` flag) rather than as an attachment — it renders directly in email clients.
3. **MIME types:** The script auto-detects MIME type from the file extension. Unknown extensions fall back to `application/octet-stream`.
4. **Sender address:** Default sender is `support@doublefin.com`. Override with `--from`.
