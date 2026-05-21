#!/usr/bin/env python3
"""Generate wrapper scripts for all Orca MCP tools."""

import json
import textwrap
from pathlib import Path


def _get_type_info(prop_def: dict) -> tuple[str, bool]:
    """Return (base_type, is_nullable) for a property definition."""
    prop_type = prop_def.get("type")
    if isinstance(prop_type, list):
        is_nullable = "null" in prop_type
        non_null_types = [t for t in prop_type if t != "null"]
        base_type = non_null_types[0] if non_null_types else "string"
        return base_type, is_nullable
    if prop_type is None:
        return "string", True
    return prop_type, False


def _build_conversion_code(prop_name: str, prop_def: dict, is_required: bool) -> str:
    """Generate Python code to convert a CSV string value to the correct type."""
    base_type, is_nullable = _get_type_info(prop_def)

    if not is_required:
        if base_type == "integer":
            return f'int(row["{prop_name}"]) if row.get("{prop_name}") else None'
        if base_type == "number":
            return f'float(row["{prop_name}"]) if row.get("{prop_name}") else None'
        if base_type == "boolean":
            return f'row["{prop_name}"].lower() in ("true", "1", "yes", "y") if row.get("{prop_name}") else None'
        if base_type == "array":
            return f'json.loads(row["{prop_name}"]) if row.get("{prop_name}") else None'
        if base_type == "object":
            return f'json.loads(row["{prop_name}"]) if row.get("{prop_name}") else None'
        # string or fallback
        return f'row["{prop_name}"] if row.get("{prop_name}") else None'

    # Required field (must be present)
    if base_type == "integer":
        return f'int(row["{prop_name}"])'
    if base_type == "number":
        return f'float(row["{prop_name}"])'
    if base_type == "boolean":
        return f'row["{prop_name}"].lower() in ("true", "1", "yes", "y")'
    if base_type == "array":
        return f'json.loads(row["{prop_name}"])'
    if base_type == "object":
        return f'json.loads(row["{prop_name}"])'
    # string or fallback
    return f'row["{prop_name}"]'


def _build_example_input_snippet(properties, required):
    if not properties:
        return "    index\n    1"
    columns = []
    for prop_name in properties:
        if prop_name in required:
            columns.append(prop_name)
        else:
            columns.append(f"{prop_name}?(optional)")
    return "    " + ",".join(columns) + "\n    " + ",".join(["..." for _ in columns])


def generate_script(tool: dict) -> str:
    """Generate a wrapper script for a single MCP tool."""
    tool_name = tool["name"]
    description = tool.get("description", f"Wrapper for MCP tool: {tool_name}")
    input_schema = tool.get("inputSchema", {})
    properties = input_schema.get("properties") or {}
    required = set(input_schema.get("required") or [])

    # Build parameter conversion code
    param_lines = []
    for prop_name in properties:
        prop_def = properties[prop_name]
        if not isinstance(prop_def, dict):
            prop_def = {}
        conversion = _build_conversion_code(prop_name, prop_def, prop_name in required)
        param_lines.append(f'            "{prop_name}": {conversion},')

    param_code = "\n".join(param_lines) if param_lines else "            # No parameters"

    has_no_params = not properties

    if has_no_params:
        body_code = """    async with get_mcp_session(args.config) as session:
        response = await call_tool_and_parse(session, TOOL_NAME, {})
        all_rows.extend(flatten_json(response))"""
    else:
        body_code = f"""    async with get_mcp_session(args.config) as session:
        for i, row in enumerate(rows):
            print(f"  Processing row {{i+1}}/{{len(rows)}}...", flush=True)
            params = {{
{param_code}
            }}
            # Remove None optional values to keep payload clean
            params = {{k: v for k, v in params.items() if v is not None}}
            response = await call_tool_and_parse(session, TOOL_NAME, params)
            if isinstance(response, dict) and "_error" in response:
                all_rows.append({{"_row": i + 1, "_error": response["_error"]}})
            else:
                all_rows.extend(flatten_json(response))"""

    # Build example snippets for the docstring
    _example_input = _build_example_input_snippet(properties, required)
    _example_output = "    result_field1,result_field2,...\n    value1,value2,..."

    custom_epilog = f"Example input CSV:\n{_example_input}\n\nExample output CSV:\n{_example_output}\n"

    script_lines = [
        "#!/usr/bin/env python3",
        f'"""{description}\n',
        "Example input CSV:",
        _example_input,
        "",
        "Example output CSV:",
        _example_output,
        '"""\n',
        "import asyncio",
        "import json",
        "import sys",
        "from pathlib import Path\n",
        'sys.path.insert(0, str(Path(__file__).resolve().parents[3]))\n',
        "from scripts.common.tools.mcp_wrapper_base import (",
        "    build_argparser,",
        "    call_tool_and_parse,",
        "    flatten_json,",
        "    get_mcp_session,",
        "    parse_csv_input,",
        "    write_csv_output,",
        ")\n",
        f'TOOL_NAME = "{tool_name}"\n',
        "\n",
        "async def main():",
        f'    parser = build_argparser(TOOL_NAME, None, {json.dumps(description)}, {json.dumps(custom_epilog)})',
        "    args = parser.parse_args()\n",
        '    print(f"Loading input CSV: {args.csv}", flush=True)',
        "    rows = parse_csv_input(args.csv, args.limit)",
        '    print(f"Loaded {len(rows)} rows", flush=True)\n',
        "    all_rows = []",
    ]

    script_lines.extend(body_code.split("\n"))

    script_lines.extend([
        "",
        '    output_path = write_csv_output(all_rows, "cache", TOOL_NAME)',
        '    print(f"Output written to: {output_path}", flush=True)',
        "\n",
        'if __name__ == "__main__":',
        "    asyncio.run(main())",
    ])

    script = "\n".join(script_lines)

    return script


def main():
    tools_json_path = Path("cache/tools.json")
    if not tools_json_path.exists():
        print(f"Error: {tools_json_path} not found")
        raise SystemExit(1)

    data = json.loads(tools_json_path.read_text())
    tools = data.get("tools", [])

    output_dir = Path("scripts/common/tools")
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    for tool in tools:
        tool_name = tool["name"]
        script_content = generate_script(tool)
        script_path = output_dir / f"mcp_{tool_name}.py"
        script_path.write_text(script_content, encoding="utf-8")
        generated.append(tool_name)
        print(f"Generated: {script_path}")

    print(f"\nGenerated {len(generated)} wrapper scripts in {output_dir}")


if __name__ == "__main__":
    main()
