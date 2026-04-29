# Send Email

## Overview

Send an email via the Orca MCP `send_email` tool. Supports plain-text and HTML bodies, CC/BCC, and file attachments of any type.

**For emails with file attachments**, always use the helper script `orca/scripts/send_email.py` — it handles base64-encoding automatically so you never have to encode files manually.

## Prerequisites

- Access to the Orca MCP server (`send_email` tool)
- Python 3 (for attachment workflow)

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
  "from": "warren@doublefin.ai",
  "to": ["recipient@example.com"],
  "subject": "Hello",
  "text": "Body here."
}
```

---

## Workflow B — Email with file attachments

Use `orca/scripts/send_email.py` to base64-encode the files, then pass the output payload to `mcp__orca__send_email`.

### Step 1: Generate the payload

```bash
python3 orca/scripts/send_email.py \
  --to recipient@example.com \
  --subject "Law Changes Report" \
  --text "Please find the report attached." \
  --attach orca/law_changes_report.html
```

### Step 2: Read the base64-encoded attachment data

The script prints a JSON object. Extract the `attachments[0].data` field (the full base64 string) and pass it to `mcp__orca__send_email` as the `data` field of the attachment.

In practice, run the script in Python and capture the output:

```python
import subprocess, json

result = subprocess.run(
    ["python3", "orca/scripts/send_email.py",
     "--to", "recipient@example.com",
     "--subject", "Report",
     "--text", "See attached.",
     "--attach", "orca/law_changes_report.html"],
    capture_output=True, text=True
)
payload = json.loads(result.stdout)
# payload is now ready to pass to mcp__orca__send_email
```

### Script options

| Flag | Description |
|---|---|
| `--to EMAIL [EMAIL ...]` | Recipient(s) — required |
| `--subject TEXT` | Subject line — required |
| `--from EMAIL` | Sender (default: `warren@doublefin.ai`) |
| `--text TEXT` | Plain-text body |
| `--html FILE` | Path to HTML file to use as email body |
| `--attach FILE [FILE ...]` | File(s) to attach (any type; auto-detected MIME) |
| `--cc EMAIL [EMAIL ...]` | CC recipients |
| `--bcc EMAIL [EMAIL ...]` | BCC recipients |

### Sending an HTML file as both body and attachment

```bash
python3 orca/scripts/send_email.py \
  --to recipient@example.com \
  --subject "Law Changes Report" \
  --html orca/law_changes_report.html \
  --attach orca/law_changes_report.html
```

---

## Important notes

1. **HTML email body vs. attachment:** If the file is an HTML email template (like a law changes report), prefer sending it as the `html` body (`--html` flag) rather than as an attachment — it renders directly in email clients.
2. **MIME types:** The script auto-detects MIME type from the file extension. Unknown extensions fall back to `application/octet-stream`.
3. **Sender address:** Default sender is `warren@doublefin.ai`. Override with `--from`.
