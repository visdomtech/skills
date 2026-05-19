# Orca

The `orca/` directory contains skill files designed to work with the **Orca MCP server** — a collection of tools for managing jurisdictions, regulations, documents, and RAG-based document search.

## MCP Server Requirement

**All Orca operations require the Orca MCP server to be configured.** Before attempting any Orca skill or tool call, verify that an MCP server named `orca` is present in the user's MCP configuration. If it is not configured:

1. **Abort the task immediately** — do not proceed with any Orca-related work
2. **Raise a clear error** to the user stating that the Orca MCP server is not configured
3. **Ask the user to configure the Orca MCP server first**, then retry the task

Do not attempt to work around a missing Orca MCP server by using alternative tools or fallback approaches.

## Skills

Before calling any MCP tool directly, **always check `orca/skills/` for an existing skill file** that covers the task. Skills encapsulate the correct workflow and must be followed — they often use helper scripts that handle details (e.g. base64 encoding for attachments) that are easy to get wrong when calling MCP tools directly.

| Task | Skill file |
|---|---|
| Send email (with or without attachments) | `orca/skills/send_email.md` |
| Generate jurisdictions data quality report | `orca/skills/jurisdictions_report.md` |
| Generate law changes report | `orca/skills/law_changes_report.md` |
| Generate document-to-RAG-file matching report | `orca/skills/document_rag_file_report.md` |
| Create RAG jurisdiction metadata for included regulations | `orca/skills/create_rag_jurisdiction_metadata.md` |
| Batch process MCP tools via Python script (saves tokens) | `orca/skills/mcp_script_runner.md` |
| Manage RAG data schemas (list, add, delete) | `orca/skills/manage_rag_data_schemas.md` |

If a skill file exists for the task, read and follow it instead of improvising with raw MCP calls.

## Scripts

The `orca/scripts/` directory contains helper scripts that automate data processing, analysis, and report generation. It is important to understand their role in the workflow:

### What Scripts Do

1. **Data Preparation**: Parse and transform large JSON responses from MCP tools into workable formats.
2. **Matching & Validation**: Compare datasets (e.g., regulations vs. documents) and identify matches or mismatches.
3. **Report Generation**: Produce HTML, CSV, or other structured outputs for human review.
4. **Payload Preparation**: Generate batch JSON payloads that *could* be sent to MCP tools, but are not sent directly by the script.

### What Scripts Do NOT Do

- **Direct MCP Tool Invocation**: Scripts run in a standard Python environment and do **not** have direct access to the MCP server. They cannot call `create_rag_metadata`, `set_rag_file_name`, or any other MCP tool directly.
- **Real-time Data Mutation**: Any action that modifies data in the Orca system (creating metadata, updating statuses, sending emails) must be performed by the agent using the appropriate MCP tool call, guided by the skill instructions.

### Scripts vs. Direct Agent MCP Calls

**All Orca skills must use Python scripts via the MCP client SDK — the agent must NOT call Orca MCP tools directly through its native tool-call capability.**

This applies to every operation, including simple one-shot reads: always run the appropriate script rather than invoking `mcp__orca__*` tools inline. This ensures consistent error handling (e.g. INTERNAL error re-verification), clear audit trails in script output, and alignment with the established workflow pattern across all skills.

### Typical Workflow

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

## MCP Tools

### Jurisdictions & Regulations

- `list_jurisdictions` — List all jurisdictions
- `upsert_jurisdiction` — Insert or update a jurisdiction (partial update on conflict)
- `list_regulations` — List regulations with filters (workspace, jurisdiction, category, status, pagination)
- `get_latest_law_changes` — Get law changes from Firestore since a given date
- `send_law_change_notifications` — Send law change email notifications via Mailgun

### Workspaces & Repositories

- `list_workspaces` — List all workspaces
- `list_repositories` — List repositories for a workspace
- `list_documents` — List documents in a repository (ordered by upload date desc)
- `create_document` — Create a new document record in a repository

### Document Processing & RAG

- `import_rag_files` — Start async GCS-to-Vertex-AI-RAG-corpus import (skips non-existent URIs)
- `get_import_rag_files_result` — Poll the status of a running RAG import
- `list_corpus` — List all RAG corpora
- `list_rag_files` — List RAG files within a corpus
- `set_rag_file_name` — Set the Vertex AI RAG file name and record processed timestamp
- `update_document_status` — Update document processing status (with optional error message)

### GCS (Google Cloud Storage)

- `list_gcs_files` — List objects under a GCS bucket path
- `check_gcs_existence` — Check which GCS URIs exist

### Email

- `send_email` — Send an email via Mailgun (text or HTML, with CC/BCC)

## Summary

Orca manages **jurisdictions** and **regulations**, organizes them into **workspaces/repositories** with **documents**, imports documents into **Vertex AI RAG** for search, tracks **law changes**, and sends **email notifications** — all backed by GCS.

## MCP Best Practices

### Default Behavior for `limit` Parameter

When calling MCP tools that accept a `limit` input parameter, **always fetch all data by default** unless the user explicitly requests a specific limit or there is a clear intentional reason to restrict results. Use `limit: 2147483647` (`0x7fffffff`, the max signed 32-bit integer) as the default value to ensure the complete dataset is returned.

## Well-Known Data

The following table documents known RAG corpora and other stable identifiers that may be referenced across skills and tools.

| Display Name | Description | Full Resource Name |
| :--- | :--- | :--- |
| `prod-s30-w1-r5-agile-wave` | RAG corpus for workspace 1, repo Default POLICY(5 POLICY) | `projects/visdomapp-1/locations/us-east4/ragCorpora/8607504787811860480` |
| `prod-s30-w1-r6-happy-quartz` | RAG corpus for workspace 1, repo Default COMPLIANCE(6 COMPLIANCE) | `projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088` |

## Dealing with Large Response Data

When Orca MCP tools return large amounts of data (e.g., thousands of jurisdictions, regulations, or documents), displaying all results at once can overwhelm users and degrade performance. Use the following strategies to handle large datasets effectively:

### Display Strategy

#### 1. Display First 10 Items
Show the first 10 records to give users immediate context about the data structure and initial content.

**Example:**
```
Showing first 10 of 1,250 jurisdictions:
1. United States of America (US)
2. Alabama (US-AL)  
3. Alaska (US-AK)
4. Arizona (US-AZ)
5. Arkansas (US-AR)
6. California (US-CA)
7. Colorado (US-CO)
8. Connecticut (US-CT)
9. Delaware (US-DE)
10. Florida (US-FL)
```

#### 2. Display Last 10 Items
Show the last 10 records to provide insight into how the data concludes or what the most recent entries look like.

**Example:**
```
Showing last 10 of 1,250 jurisdictions:
1,241. Wyoming (US-WY)
1,242. Puerto Rico (US-PR)
1,243. Virgin Islands (US-VI)
1,244. Guam (US-GU)
1,245. American Samoa (US-AS)
1,246. Northern Mariana Islands (US-MP)
1,247. District of Columbia (US-DC)
1,248. Marshall Islands (MH)
1,249. Micronesia (FM)
1,250. Palau (PW)
```

#### 3. Display Random Middle 10 Items
Sample 10 random records from the middle portion of the dataset to show diversity and variation within the data.

**Example:**
```
Showing 10 random sample items from middle of 1,250 jurisdictions:
- Texas (US-TX)
- Ontario (CA-ON)
- Bavaria (DE-BY)
- Tokyo (JP-13)
- New South Wales (AU-NSW)
- São Paulo (BR-SP)
- Gauteng (ZA-GT)
- Île-de-France (FR-IDF)
- Lombardy (IT-25)
- Punjab (IN-PB)
```

#### 4. Provide Summary Statistics
Give comprehensive summary information about the complete dataset:

**Example:**
```
Dataset Summary:
- Total records: 1,250 jurisdictions
- Data types: Federal (50), State/Province (1,200)
- Geographic coverage: 195 countries
- Most common jurisdiction type: State/Province (96%)
- Date range: Created between 2025-11-19 and 2026-04-17
- Average population per jurisdiction: 8.2M
- Largest jurisdiction: India (1.38B population)
- Smallest jurisdiction: Vatican City (825 population)
```

### Implementation Guidelines

#### When to Apply This Strategy
- Response size exceeds 50 records
- Response data size exceeds 10KB
- User query doesn't specify pagination parameters
- Performance impact is noticeable

#### How to Implement
1. **Count total records** before processing display logic
2. **Apply sampling strategy** based on data characteristics:
   - Sequential data: Use first/last approach
   - Categorical data: Use random sampling
   - Time-series data: Use first/last + middle samples
3. **Generate meaningful summary** with relevant statistics
4. **Provide navigation options** for users who want more details:
   - "Show all" (with warning about size)
   - "Show specific page/range"
   - "Filter by criteria"

### User Experience Considerations
- Always inform users about the total dataset size
- Clearly indicate when showing partial results
- Offer clear paths to access complete data if needed
- Prioritize performance over completeness for initial display
- Cache sampled views for consistent user experience
