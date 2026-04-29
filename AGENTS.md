# Doublefin Skills

This repository contains skill files for use with **Doublefin** services.

## Organization

Each Doublefin service has its skill files placed in a directory named after the service. For example, skill files for the **Orca** service are all located under `orca/`.

## Usage

When using skills for a service, always include and respect the `AGENTS.md` file in that service's directory. For example, when working with the Orca service, follow the guidance in `orca/AGENTS.md`.

## Service Routing Protocol

When a user's prompt is formatted like `[service]: question text`, the system should:

1. **Load Service AGENTS.md**: First load and respect the `AGENTS.md` file from the directory `[service]/`
2. **Search Existing Skills**: Look for existing skill Markdown files inside the `[service]/skills/` directory that can handle or related to the task
3. **Check MCP Tools**: If no existing skills are found, check the MCP tools' definitions from the MCP server named `[service]` to determine available capabilities
