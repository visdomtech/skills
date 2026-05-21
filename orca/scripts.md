# Scripts Guide

The `orca/scripts/` directory contains helper scripts that automate data processing, analysis, and report generation.

## What Scripts Do

1. **Data Preparation**: Parse and transform large JSON responses from MCP tools into workable formats.
2. **Matching & Validation**: Compare datasets (e.g., regulations vs. documents) and identify matches or mismatches.
3. **Report Generation**: Produce HTML, CSV, or other structured outputs for human review.
4. **Payload Preparation**: Generate batch JSON payloads that *could* be sent to MCP tools, but are not sent directly by the script.

## What Scripts Do NOT Do

- **Direct MCP Tool Invocation**: Scripts run in a standard Python environment and do **not** have direct access to the MCP server. They cannot call `create_rag_metadata`, `set_rag_file_name`, or any other MCP tool directly.
- **Real-time Data Mutation**: Any action that modifies data in the Orca system must be performed by the agent using the appropriate MCP tool call, guided by the skill instructions.

## Scripts vs. Direct Agent MCP Calls

**All Orca skills must use Python scripts via the MCP client SDK — the agent must NOT call Orca MCP tools directly through its native tool-call capability.**

This applies to every operation, including simple one-shot reads: always run the appropriate script rather than invoking `mcp__orca__*` tools inline. This ensures consistent error handling, clear audit trails in script output, and alignment with the established workflow pattern across all skills.

## Typical Workflow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Fetch Data     │────▶│  Run Script      │────▶│  Agent invokes  │
│  (MCP Tools)    │     │  (Analysis/Prep) │     │  MCP Tools      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                                ┌─────────────────┐
                                                │  Verify Result  │
                                                │  (MCP Tools)    │
                                                └─────────────────┘
```

1. The agent fetches data using MCP tools (e.g., `list_regulations`, `list_documents`).
2. The agent saves the raw JSON and runs a script to analyze it (e.g., matching filenames).
3. The script outputs a summary of what actions are needed.
4. The agent then invokes the relevant MCP tools directly (e.g., `create_rag_metadata`) based on the script's findings.
5. Finally, the agent verifies the result using MCP tools (e.g., `list_rag_metadata`).

---

## MCP Tool Wrappers

The `orca/scripts/common/tools/` directory contains **MCP tool wrapper scripts** — one for each Orca MCP tool. These wrappers provide a consistent CSV-in/CSV-out interface for batch operations and simplify token usage when processing multiple rows.

### What They Do

1. **CSV Input**: Accept an input CSV with parameters for the MCP tool call (one row per invocation)
2. **Batch Processing**: Iterate over all rows in the CSV, calling the MCP tool once per row
3. **CSV Output**: Write results to an output CSV under `orca/cache/[tool_name]/`
4. **Limit Support**: Accept a `--limit N` flag to process only the first N rows (useful for verification)
5. **Error Handling**: Centralized error handling and logging via `mcp_wrapper_base.py`

### When to Use

- **Batch Operations**: When you need to call the same MCP tool multiple times with different parameters
- **Token Efficiency**: Wrapper scripts reduce token consumption compared to inline MCP calls
- **Audit Trail**: CSV output provides a persistent record of all operations performed
- **Verification First**: Always test with `--limit 1` before running on the full dataset

### Available Wrappers

Every Orca MCP tool has a corresponding wrapper script in `scripts/common/tools/mcp_<tool_name>.py`.

### Usage

```bash
# Prepare input CSV
cat > /tmp/input.csv <<EOF
workspaceId,repositoryId,limit
1,6,2147483647
EOF

# Verify with one row first
uv run python scripts/common/tools/mcp_list_documents.py \
  --config assets/mcp_config.json --csv /tmp/input.csv --limit 1

# Process all rows
uv run python scripts/common/tools/mcp_list_documents.py \
  --config assets/mcp_config.json --csv /tmp/input.csv

# Check output under orca/cache/mcp_list_documents/
```

Each wrapper includes built-in help:

```bash
uv run python scripts/common/tools/mcp_list_documents.py --help
```

### Base Module

All wrappers share utilities from `scripts/common/tools/mcp_wrapper_base.py`:

- `get_mcp_session()` — Manages MCP session lifecycle with configurable timeout
- `parse_csv_input()` — Reads and validates input CSV files
- `write_csv_output()` — Writes flattened JSON results to output CSV
- `call_tool_and_parse()` — Calls an MCP tool and parses the response
- `_parse_content()` — Extracts content from MCP tool results

**Do not modify wrapper scripts directly.** If you need custom behavior, create a new script in `orca/scripts/` that imports from `mcp_wrapper_base.py`.
