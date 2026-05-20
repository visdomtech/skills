# Orca MCP Tools Guide

Complete reference for the 31 tools exposed by the `orca` MCP server.

**Server metadata:** `name: orca`, `source: user`, `toolCount: 31`

**Raw schema:** [`tools.json`](./cache/tools.json)

---

## Table of Contents

- [Global Conventions](#global-conventions)
- [Jurisdictions & Regulations](#jurisdictions--regulations)
- [Workspaces & Repositories](#workspaces--repositories)
- [Document Processing & RAG](#document-processing--rag)
- [GCS (Google Cloud Storage)](#gcs-google-cloud-storage)
- [Email](#email)
- [Regulation-Law Matching](#regulation-law-matching)
- [Agent Configuration](#agent-configuration)

---

## Global Conventions

### Default `limit` Behavior

When a tool accepts `limit`, **fetch all data by default** unless the user explicitly requests a restriction. Use `2147483647` (`0x7fffffff`, max signed 32-bit integer) as the default.

### Dealing with Large Responses

When responses exceed 50 records or 10 KB, use a sampling strategy instead of dumping everything:

1. Show the **first 10** items
2. Show the **last 10** items
3. Show **10 random middle** items
4. Provide **summary statistics** (total count, categories, date ranges, etc.)

---

## Jurisdictions & Regulations

### `list_jurisdictions`

List all jurisdictions ordered by type and name.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

**Returns:** All jurisdictions (potentially thousands). Apply large-response sampling.

---

### `upsert_jurisdiction`

Insert or update a jurisdiction. On code conflict, NULL fields preserve the existing value (partial update). Returns the `jurisdiction_id`.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `code` | Yes | `string` | Unique jurisdiction code |
| `jurisdictionType` | Yes | `string` | Type of jurisdiction |
| `name` | Yes | `string` | Display name |
| `aliases` | No | `string[]` | Alternative names |
| `fipsCode` | No | `string` | FIPS code |
| `fullName` | No | `string` | Full official name |
| `laborDeptUrl` | No | `string` | Labor department URL |
| `metadata` | No | `string` | Free-form metadata JSON/string |
| `parentJurisdictionId` | No | `integer` | Parent jurisdiction ID |
| `population` | No | `integer` | Population count |
| `timezone` | No | `string` | Timezone identifier |
| `websiteUrl` | No | `string` | Official website URL |

---

### `list_regulations`

List regulations with optional filters. Supports cursor-based pagination.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | Yes | `integer` | Workspace ID for inclusion check |
| `limit` | Yes | `integer` | Max results to return |
| `afterJurisdictionId` | No | `integer` | Cursor: jurisdiction ID of last seen regulation |
| `afterShortTitle` | No | `string` | Cursor: short title of last seen regulation |
| `category` | No | `string` | Filter by regulation category |
| `included` | No | `boolean` | Filter by workspace inclusion status |
| `jurisdictionId` | No | `integer` | Filter by jurisdiction ID |
| `status` | No | `string` | Filter by regulation status |

**Tip:** Use `limit: 2147483647` to fetch the complete set unless pagination is intentional.

---

### `get_latest_law_changes`

Get latest law changes from Firestore since a given date. Only changes with `revised_enactment_date >= sinceDate` are returned.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `sinceDate` | Yes | `string` | ISO date string (e.g. `2025-01-01`) |
| `changeType` | No | `string` | Filter by change type |
| `jurisdiction` | No | `string` | Filter by jurisdiction code/name |

---

### `send_law_change_notifications`

Send email notifications about law changes since a given date via Mailgun.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `sinceDate` | Yes | `string` | ISO date string |
| `recipients` | Yes | `string[]` | Email addresses |
| `changeType` | No | `string` | Filter by change type |
| `jurisdiction` | No | `string` | Filter by jurisdiction |
| `subject` | No | `string` | Custom email subject |

---

## Workspaces & Repositories

### `list_workspaces`

List all workspaces.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

---

### `list_repositories`

List all repositories for a workspace.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | No | `integer` | Workspace ID (nullable) |

---

### `list_documents`

List documents in a repository ordered by upload date descending.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | Yes | `integer` | Workspace ID |
| `repositoryId` | Yes | `integer` | Repository ID |
| `limit` | Yes | `integer` | Max results to return |

**Tip:** Use `limit: 2147483647` to fetch the complete set.

---

### `create_document`

Create a new document record in a repository and return its `document_id`.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | Yes | `integer` | Workspace ID |
| `repositoryId` | Yes | `integer` | Repository ID |
| `filename` | Yes | `string` | File name |
| `documentType` | Yes | `string` | Document type |
| `uploadedBy` | Yes | `integer` | User ID of uploader |
| `gsUri` | Yes | `string` | GCS URI (`gs://bucket/path`) |
| `fileReferenceId` | No | `integer` | Reference to an existing file record |
| `fileSizeBytes` | No | `integer` | File size in bytes |

---

## Document Processing & RAG

### `import_rag_files`

Start an async GCS-to-RAG-corpus import. Non-existent URIs are skipped and reported in `nonExist`. Returns `operationName` immediately; poll with `get_import_rag_files_result`.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `corpusName` | Yes | `string` | Full RAG corpus resource name |
| `gcsUris` | Yes | `string[]` | Array of GCS URIs to import |

**Workflow:**
1. Call `import_rag_files`
2. Poll `get_import_rag_files_result` until `done == true`
3. Handle any URIs reported in `nonExist`

---

### `get_import_rag_files_result`

Poll the result of the running `import_rag_files` operation.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters; uses server-side operation state |

**Returns:** `done=false` while still in progress.

---

### `list_corpus`

List all RAG corpora in the configured Vertex AI location.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

**Well-known corpora:**

| Display Name | Description | Full Resource Name |
| :--- | :--- | :--- |
| `prod-s30-w1-r5-agile-wave` | RAG corpus for workspace 1, repo Default POLICY(5 POLICY) | `projects/visdomapp-1/locations/us-east4/ragCorpora/8607504787811860480` |
| `prod-s30-w1-r6-happy-quartz` | RAG corpus for workspace 1, repo Default COMPLIANCE(6 COMPLIANCE) | `projects/visdomapp-1/locations/us-east4/ragCorpora/3419358017081049088` |

---

### `list_rag_files`

List RAG files within a corpus.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `corpusName` | Yes | `string` | Full corpus resource name |

---

### `set_rag_file_name`

Set the Vertex AI RAG file name for a document and record the processed timestamp.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | Yes | `integer` | Workspace ID |
| `entries` | Yes | `object[]` | Batch of document-to-RAG mappings |
| `entries[].documentId` | Yes | `integer` | Document ID |
| `entries[].ragFileName` | Yes | `string` | RAG file resource name |

---

### `update_document_status`

Update the processing status and optional error message of one or more documents.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `workspaceId` | Yes | `integer` | Workspace ID |
| `documentIds` | Yes | `integer[]` | Documents to update |
| `status` | Yes | `string` | New status value |
| `errorMessage` | No | `string` | Optional error message |

---

### `create_rag_data_schema`

Create a typed data schema key on a RAG corpus. Must exist before creating metadata with that key.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `corpusName` | Yes | `string` | Full corpus resource name |
| `key` | Yes | `string` | Schema key name |
| `dataType` | Yes | `string` | Data type (`string`, `integer`, `float`, `boolean`) |
| `granularity` | No | `string` | Granularity level |

---

### `list_rag_data_schemas`

List all data schema keys defined on a RAG corpus.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `corpusName` | Yes | `string` | Full corpus resource name |

---

### `delete_rag_data_schema`

Delete a data schema from a RAG corpus by its full resource name.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `name` | Yes | `string` | Full resource name of the data schema |

---

### `create_rag_metadata`

Attach metadata to a RAG file. The key must match an existing data schema on the corpus.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `ragFileName` | Yes | `string` | Full RAG file resource name |
| `entries` | Yes | `object[]` | Metadata entries |
| `entries[].key` | Yes | `string` | Schema key |
| `entries[].valueStr` | No | `string` | String value |
| `entries[].valueInt` | No | `integer` | Integer value |
| `entries[].valueFloat` | No | `number` | Float value |
| `entries[].valueBool` | No | `boolean` | Boolean value |

**Note:** Provide exactly one value field per entry matching the schema's `dataType`.

---

### `list_rag_metadata`

List all metadata entries attached to a RAG file.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `ragFileName` | Yes | `string` | Full RAG file resource name |

---

### `update_rag_metadata`

Replace the value of an existing RAG file metadata entry.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `name` | Yes | `string` | Full resource name of the metadata entry |
| `key` | Yes | `string` | Schema key |
| `valueStr` | No | `string` | String value |
| `valueInt` | No | `integer` | Integer value |
| `valueFloat` | No | `number` | Float value |
| `valueBool` | No | `boolean` | Boolean value |

---

### `delete_rag_metadata`

Delete a metadata entry from a RAG file by its full resource name.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `name` | Yes | `string` | Full resource name of the metadata entry |

---

## GCS (Google Cloud Storage)

### `list_gcs_files`

List all object names under a GCS bucket path.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `gcsUri` | Yes | `string` | GCS URI prefix (e.g. `gs://bucket/prefix/`) |

---

### `check_gcs_existence`

Check which GCS URIs exist and which do not.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `gcsUris` | Yes | `string[]` | Array of GCS URIs to verify |

**Returns:** Separated lists of existing and non-existing URIs.

---

## Email

### `send_email`

Send an email via Mailgun. At least one of `text` or `html` must be provided. Attachments are passed as base64-encoded data.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `from` | Yes | `string` | Sender email address |
| `to` | Yes | `string[]` | Recipient email addresses |
| `subject` | Yes | `string` | Email subject |
| `text` | No | `string` | Plain-text body |
| `html` | No | `string` | HTML body |
| `cc` | No | `string[]` | CC recipients |
| `bcc` | No | `string[]` | BCC recipients |
| `attachments` | No | `object[]` | Attachments |
| `attachments[].filename` | Yes | `string` | File name |
| `attachments[].contentType` | Yes | `string` | MIME type |
| `attachments[].data` | Yes | `string` | Base64-encoded file data |
| `attachments[].inline` | No | `boolean` | Whether the attachment is inline |

**Skill reference:** For the complete email workflow (including base64 encoding for attachments), use the `send_email` skill instead of calling this tool directly.

---

## Regulation-Law Matching

### `list_structure_laws_for_matching`

List structure laws that are not yet matched to any regulation.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

---

### `list_unmatched_regulations`

List regulations that have no associated structure laws.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

---

### `apply_proposed_matching`

Insert regulation-to-law matches in batch, ignoring duplicates.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `matches` | Yes | `object[]` | Array of match pairs |
| `matches[].regulationId` | Yes | `integer` | Regulation ID |
| `matches[].lawId` | Yes | `integer` | Structure law ID |

---

## Agent Configuration

### `list_agent_configs`

List all AgentConfig documents in Firestore.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| *(none)* | — | — | No parameters |

**Returns:** Same fields as `get_agent_config` for every agent.

---

### `get_agent_config`

Get the AgentConfig for an orcaagents agent by ID.

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `agentId` | Yes | `string` | Agent identifier |

**Returns:** `systemPrompt`, `model`, `enabled`, `includeThoughts`, `thinkingBudget`.

---

### `set_agent_config`

Partially update the AgentConfig for an orcaagents agent. Only supplied fields are written (Firestore MergeAll).

| Parameter | Required | Type | Description |
|-----------|----------|------|-------------|
| `agentId` | Yes | `string` | Agent identifier |
| `systemPrompt` | No | `string` | System prompt text |
| `model` | No | `string` | Model identifier |
| `enabled` | No | `boolean` | Whether the agent is active |
| `includeThoughts` | No | `boolean` | Include thinking in responses |
| `thinkingBudget` | No | `integer` | Thinking budget (tokens) |

**Important:** Call `POST /api/config/reload` on the orcaagents service separately to apply the new config.

---

## Summary by Category

| Category | Tools | Read / Write |
|----------|-------|--------------|
| Jurisdictions & Regulations | `list_jurisdictions`, `upsert_jurisdiction`, `list_regulations`, `get_latest_law_changes`, `send_law_change_notifications` | 3 read / 2 write |
| Workspaces & Repositories | `list_workspaces`, `list_repositories`, `list_documents`, `create_document` | 3 read / 1 write |
| Document Processing & RAG | `import_rag_files`, `get_import_rag_files_result`, `list_corpus`, `list_rag_files`, `set_rag_file_name`, `update_document_status`, `create_rag_data_schema`, `list_rag_data_schemas`, `delete_rag_data_schema`, `create_rag_metadata`, `list_rag_metadata`, `update_rag_metadata`, `delete_rag_metadata` | 7 read / 6 write |
| GCS | `list_gcs_files`, `check_gcs_existence` | 2 read / 0 write |
| Email | `send_email`, `send_law_change_notifications` | 0 read / 2 write |
| Matching | `list_structure_laws_for_matching`, `list_unmatched_regulations`, `apply_proposed_matching` | 2 read / 1 write |
| Agent Configuration | `list_agent_configs`, `get_agent_config`, `set_agent_config` | 2 read / 1 write |
