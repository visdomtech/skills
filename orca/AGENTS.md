# Orca

The `orca/` directory contains skill files designed to work with the **Orca MCP server** — a collection of tools for managing jurisdictions, regulations, documents, and RAG-based document search.

---

## MUST: Check MCP Server First

**All Orca operations require the Orca MCP server to be configured.**

Before attempting any Orca-related work:

1. Verify an MCP server named `orca` is present in the user's MCP configuration
2. **If not configured: abort the task, raise a clear error, and ask the user to configure the Orca MCP server first**
3. Do not attempt workarounds, fallback approaches, or alternative tools

---

## MUST: Check Skills Before Calling Tools

Before calling any MCP tool directly, **always check `orca/skills/` for an existing skill file** that covers the task. Skills encapsulate the correct workflow and must be followed.

| Task | Skill file |
|---|---|
| Send email (with or without attachments) | `orca/skills/send_email.md` |
| Generate jurisdictions data quality report | `orca/skills/jurisdictions_report.md` |
| Generate law changes report | `orca/skills/law_changes_report.md` |
| Generate document-to-RAG-file matching report | `orca/skills/document_rag_file_report.md` |
| Create RAG jurisdiction metadata for included regulations | `orca/skills/create_rag_jurisdiction_metadata.md` |
| Batch process MCP tools via Python script (saves tokens) | `orca/skills/mcp_script_runner.md` |
| Manage RAG data schemas (list, add, delete) | `orca/skills/manage_rag_data_schemas.md` |

---

## MUST NOT: Call MCP Tools Inline

**The agent must NOT call Orca MCP tools directly through its native tool-call capability.** Always run the appropriate script via the MCP client SDK instead.

This ensures consistent error handling, clear audit trails in script output, and alignment with the established workflow pattern across all skills.

### Why Scripts Over Inline Calls?

- **Error handling**: Scripts handle `INTERNAL` errors and re-verification consistently
- **Audit trail**: Script output provides a clear record of what was done
- **Workflow alignment**: All skills follow the same script-based pattern

See [`scripts.md`](./scripts.md) for the full scripts guide, including MCP tool wrappers.

---

## MUST: Fetch All Data by Default

When calling MCP tools that accept a `limit` input parameter, **always fetch all data by default** unless the user explicitly requests a specific limit or there is a clear intentional reason to restrict results.

Use `limit: 2147483647` (`0x7fffffff`, the max signed 32-bit integer) as the default value to ensure the complete dataset is returned.

---

## MUST: Handle Large Responses Properly

When responses exceed 50 records or 10KB, **do not dump everything**. Instead, apply a sampling strategy:

1. Show the **first 10** items
2. Show the **last 10** items
3. Show **10 random middle** items
4. Provide **summary statistics** (total count, categories, date ranges, etc.)

See [`display-strategies.md`](./display-strategies.md) for detailed implementation guidance and examples.

---

## Reference

| Topic | File |
|---|---|
| MCP tool reference (parameters, types, descriptions) | [`tools.md`](./tools.md) |
| Scripts, MCP tool wrappers, and workflow | [`scripts.md`](./scripts.md) |
| Large response display strategies | [`display-strategies.md`](./display-strategies.md) |
| Skill files (task-specific workflows) | [`skills/`](./skills/) |

---

## Summary

Orca manages **jurisdictions** and **regulations**, organizes them into **workspaces/repositories** with **documents**, imports documents into **Vertex AI RAG** for search, tracks **law changes**, and sends **email notifications** — all backed by GCS.

| RAG Corpus | Description | Full Resource Name |
| :--- | :--- | :--- |
| `prod-s30-w1-r5-agile-wave` | Workspace 1, repo Default POLICY(5 POLICY) | `projects/visdomapp-1/locations/us-east4/ragCorpora/8607504787811860480` |
| `prod-s30-w1-r6-happy-quartz` | Workspace 1, repo Default COMPLIANCE(6 COMPLIANCE) | `projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088` |
