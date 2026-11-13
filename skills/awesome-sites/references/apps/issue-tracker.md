# Issue Tracker on Sites

Build a working tracker in one pass without stopping to ask about product details. Use the official `sites` skill for project setup, registration, dependencies, build, packaging, and publishing. This skill only defines what to build. If the Sites skill or Sites tools are unavailable, tell the user and stop.

## Defaults

Use these unless the user says otherwise.

- **Audience:** private (owner-only). For team use, keep it private and add people through Sites access settings. Everyone with access shares one board.
- **Stack:** Vinext starter with a D1 binding named `DB`. R2 is not needed.
- **Identity:** Sign in with ChatGPT. Store the creator as `oai-authenticated-user-id` and show the email. Require identity for every write and return 401 without it.
- **MCP:** enabled with `capabilities: ["mcp"]`.
- **Look:** dense, quiet, Linear-like. Neutral gray, one accent color, small type, minimal borders. Support dark mode.

## Data

- **projects:** id, key (2–5 uppercase letters, unique), name, created_at
- **issues:** id, project_id, number (sequential within a project), title, description (markdown), status (`backlog` `todo` `in_progress` `done` `canceled`), priority (0 none, 1 urgent, 2 high, 3 medium, 4 low), labels (JSON text array), assignee_email (nullable), creator_id, sort_order (real), created_at, updated_at, completed_at
- **comments:** id, issue_id, author_id, author_email, body, created_at

Show issues as `KEY-number`, for example `ENG-12`. Assign the number and insert the issue in the same D1 batch so numbers do not collide.

## Screens

- **Board `/`:** one column per status, with drag-and-drop between columns. Filter by project, label, assignee, and priority; search by title. Remember the last filter in the URL.
- **Issue `/issues/[identifier]`:** edit title, description, status, priority, labels, and assignee inline. Show comments.
- **Shortcuts:** `c` new issue, `/` search, `j`/`k` move between issues, `1`–`5` change status of the selected issue.
- **First run:** if there are no projects, show only a form to create the first project.

## MCP tools

Return compact JSON that includes `identifier` and the issue URL. Keep tool discovery free of private data, and mark read-only tools as read-only.

- `list_issues`: filter by project, status, assignee, or query; limit 50
- `get_issue`: one issue by `identifier`, with comments
- `create_issue`: project key, title, optional description, priority, labels, status
- `update_issue`: change any editable field by `identifier`
- `add_comment`: add a comment by `identifier`

## Done when

- The build passes and a private deployment URL is returned.
- In the deployed site: sign in, create a project, create an issue, move it to another status, and comment. Everything persists after reload.
- MCP: show the user how to connect the Site plugin. After they connect, one `list_issues` call returns the issue you created. Until then, report the connection as pending, separately from the deployment.

## Out of scope

Do not build real-time co-editing, offline sync, GitHub/Slack integrations, email notifications, or cycles and roadmaps. If the user asks for one of these, say it is outside this skill and suggest a smaller version that fits Sites.
