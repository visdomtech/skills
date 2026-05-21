# Agent Config Management

## Overview

This skill describes how to read and write the runtime configuration (`AgentConfig`) for agents
in the **orcaagents** service using the Orca MCP tools `get_agent_config` and `set_agent_config`.

All MCP communication is handled via `scripts/common/tools/mcp_wrapper_base.py`.

Config changes are persisted to Firestore immediately and take effect on the next agent request.

## Prerequisites

- Access to the Orca MCP server
- The `get_agent_config` and `set_agent_config` tools

## Known Agent IDs

| Agent ID | Role |
|---|---|
| `legal-coordinator` | Orchestrates the legal research pipeline |
| `rag-coordinator` | Orchestrates the RAG retrieval pipeline |
| `legal-expert` | Performs deep legal analysis |
| `clarilex` | Provides plain-language legal explanations |
| `research` | Conducts research queries |
| `retrieve` | Retrieves documents from the RAG corpus |
| `augment` | Augments retrieved content |
| `synthesis` | Synthesizes multi-source answers |
| `mediator` | Routes between the legal and RAG coordinators |
| `rag-lite` | Lightweight RAG-only agent |

## AgentConfig Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `systemPrompt` | string | `""` | LLM system prompt. Overrides the agent's hardcoded instruction when non-empty. |
| `model` | string | `""` | Model name, e.g. `"gemini-2.5-flash"`. Empty uses the service default. |
| `enabled` | bool | `true` | If `false`, the agent is disabled. |
| `includeThoughts` | bool | `true` | Whether thinking tokens are included in the agent output. |
| `thinkingBudget` | int | `0` | Token budget for thinking. `0` means no budget cap. |

## Step 1: Read the Current Config

Call `get_agent_config` with the target agent ID:

```json
{
  "agentId": "legal-expert"
}
```

Example response:

```json
{
  "agentId": "legal-expert",
  "systemPrompt": "You are a senior labor law attorney...",
  "model": "gemini-2.5-flash",
  "enabled": true,
  "includeThoughts": true,
  "thinkingBudget": 8000
}
```

**Note:** If the document does not exist in Firestore, the tool returns an error. The orcaagents
service will use `DefaultAgentConfig` at runtime (`enabled: true, includeThoughts: true`).

## Step 2: Update the Config

Call `set_agent_config` with only the fields you want to change. Omitted fields are preserved —
the write is a Firestore merge, not a full replace.

### Example A — Change the system prompt only

```json
{
  "agentId": "legal-expert",
  "systemPrompt": "You are a senior labor law attorney specializing in California wage and hour law..."
}
```

### Example B — Disable an agent

```json
{
  "agentId": "synthesis",
  "enabled": false
}
```

### Example C — Change model and thinking budget

```json
{
  "agentId": "clarilex",
  "model": "gemini-2.5-pro",
  "thinkingBudget": 16000
}
```

Example response:

```json
{
  "agentId": "clarilex",
  "updated": ["model", "thinkingBudget"]
}
```

## Typical Workflow

1. Call `get_agent_config` to inspect the current state.
2. Decide what to change.
3. Call `set_agent_config` with only the changed fields.
4. Verify by calling `get_agent_config` again.

## Key Notes

1. **Always read before writing** — inspect the current config so you do not unintentionally
   overwrite fields you did not intend to change.
2. **`set_agent_config` is a merge, not a replace** — only the fields you supply are updated.
3. **Agent IDs are case-sensitive** — always use the exact hyphenated ID from the table above.
4. **`thinkingBudget: 0` means no cap** — set to a positive integer (e.g. `8000`) to enforce
   a token budget for the agent's thinking step.
