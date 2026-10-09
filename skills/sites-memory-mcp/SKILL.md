---
name: sites-memory-mcp
description: Build and publish a personal memory MCP server on ChatGPT Sites so ChatGPT and Codex can save and recall notes across conversations, with a small web UI for review. Use when the user wants a remote memory, notes, or knowledge MCP server hosted on Sites.
---

# Memory MCP on Sites

Build a working MCP server and its web UI in one pass. Use the official `sites` skill for project setup, registration, dependencies, build, packaging, publishing, and plugin connection. This skill only defines what to build. If the Sites skill or Sites tools are unavailable, tell the user and stop.

## Defaults

- **Audience:** private (owner-only).
- **Stack:** Vinext starter with a D1 binding named `DB`, plus MCP via `capabilities: ["mcp"]` and a stateless `POST /mcp`.
- **Ownership:** every memory belongs to one `oai-authenticated-user-id`. Every tool and page reads and writes only the caller's records. Return 401 when identity is missing. Service access without a user identity cannot read memories.
- **Search:** case-insensitive substring match on content and tags. This is enough for personal scale. Add other search only if the user asks and the build verifies it.

## Data

- **memories:** id, owner_id, content (max 4,000 characters), tags (JSON text array, lowercase), source (`chatgpt` `codex` `web` or free text), pinned (boolean), created_at, updated_at

## MCP tools

Tool descriptions are what make the model use the tools. State when to call each one, for example: "Call `remember` when the user states a durable preference, fact, or decision they want kept."

- `remember`: content, optional tags and source. Returns id.
- `recall`: query and/or tags, limit up to 20. Pinned memories first, then most recent. Read-only.
- `list_recent`: limit up to 20. Read-only.
- `update_memory`: id with new content, tags, or pinned.
- `forget`: id. Deletes permanently.

Keep tool discovery free of private data.

## Web UI

- **`/`:** search box, tag filter, pinned section, then a recent list. Edit content and tags inline, toggle pinned, delete with confirmation.
- **Connect panel:** short steps for connecting the Site plugin in ChatGPT or Codex (Plugins > Personal > Created by you).
- **Look:** clean single column, readable at phone width.

## Done when

- The build passes and a private deployment URL is returned.
- In the deployed site: sign in, add a memory, edit it, pin it, search for it, and delete it. Changes persist after reload.
- MCP: show the plugin connection UI. After the user connects, `remember` then `recall` returns the saved memory. Until then, report the connection as pending, separately from the deployment.

## Out of scope

Do not build embeddings or semantic search, file attachments, sharing between users, or automatic summarization with paid model calls. If the user asks, give the cost and the change needed before building any of these.
