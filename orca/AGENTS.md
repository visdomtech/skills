# Orca

The `orca/` directory contains skill files designed to work with the **Orca MCP server** — a collection of tools for managing jurisdictions, regulations, documents, and RAG-based document search.

## MCP Server Requirement

**All Orca operations require the Orca MCP server to be configured.** Before attempting any Orca skill or tool call, verify that an MCP server named `orca` is present in the user's MCP configuration. If it is not configured:

1. **Abort the task immediately** — do not proceed with any Orca-related work
2. **Raise a clear error** to the user stating that the Orca MCP server is not configured
3. **Ask the user to configure the Orca MCP server first**, then retry the task

Do not attempt to work around a missing Orca MCP server by using alternative tools or fallback approaches.

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

## Caching Policy

All Orca MCP tool responses are cached according to the following policy to improve performance and reduce redundant API calls.

### Cache Behavior

All responses from Orca tool calls MUST be cached with the following rules:

1. **Cache Duration**: All cached responses expire after **1 day (24 hours)** from the time of creation
2. **Cache Usage Priority**: Unless the cache has expired OR the user explicitly requests fresh data, ALWAYS use the cached content
3. **Standardized Cache Location**: Cache files MUST be stored in `[service]/cache` directory, where `[service]` is the directory of the given service (e.g., `orca`)

### Cache Key Generation

Each tool request must be mapped to a unique cache key using the following formula:

```
cache_key = SHA256(tool_name + JSON.stringify(sorted_parameters))
```

Where:
- `tool_name`: The exact raw tool name as returned from the MCP server. Do NOT add any prefix such as `mcp_` or modify the name in any way.
- `sorted_parameters`: All parameters passed to the tool, sorted alphabetically by key and serialized to JSON

### Cache File Structure

Cache files are stored as JSON files with the following structure:

```json
{
  "cache_version": "1.0",
  "tool_name": "tool_name_here",
  "parameters": {
    "param1": "value1",
    "param2": "value2"
  },
  "response": {
    "data": "actual_tool_response_data",
    "metadata": {
      "cached_at": "ISO8601_timestamp",
      "expires_at": "ISO8601_timestamp_plus_24h"
    }
  }
}
```

### Cache File Naming

Cache files are named using the format:
```
orca_cache_{cache_key_first_16_chars}.json
```

Example: `orca_cache_a1b2c3d4e5f6g7h8.json`

**Note**: Files are no longer hidden (no leading dot) since they are stored in a dedicated cache directory

### Cache Operations

#### Reading from Cache
1. Generate cache key from current tool request
2. Identify the service directory as the directory containing this `tool_response_cache.md` file
3. Check if cache file exists in `[service]/cache/` directory
4. If file exists, verify it hasn't expired (compare current time with `expires_at`)
5. If valid, return cached response immediately
6. If expired or missing, proceed with actual tool call

#### Writing to Cache
1. After successful tool call, create cache file with structure above
2. Set `cached_at` to current ISO8601 timestamp
3. Set `expires_at` to current time + 24 hours
4. Ensure `[service]/cache/` directory exists (create if necessary)
5. Save file in `[service]/cache/` directory with appropriate naming

### Cache Invalidation

Cache can be bypassed/expired in these scenarios:
- User explicitly requests "fresh", "uncached", or "no-cache" data
- Cache file is older than 24 hours
- Cache file is corrupted or unreadable
- User deletes cache files manually

---

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
