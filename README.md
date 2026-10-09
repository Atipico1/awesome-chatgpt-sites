# awesome-chatgpt-sites

App-building skills for [ChatGPT Sites](https://learn.chatgpt.com/docs/sites), OpenAI's hosting for sites built in ChatGPT and Codex. (This is not a list of ChatGPT mirror sites.)

Each skill builds one specific app (a personal web app or an MCP server) and publishes it to Sites in one pass. The skills fix the product decisions: scope, data model, screens, MCP tools, and done criteria. The official Sites skill handles setup, build, and publishing.

## Skills

| Skill | Builds | Type |
| --- | --- | --- |
| [sites-issue-tracker](skills/sites-issue-tracker/SKILL.md) | Linear-style issue board with MCP tools | Web app + MCP |
| [sites-memory-mcp](skills/sites-memory-mcp/SKILL.md) | Personal memory that ChatGPT and Codex can read and write | MCP server + web UI |

## Requirements

- Codex with the official **Sites** plugin installed and enabled
- A ChatGPT plan with Sites access (Plus, Pro, or an eligible workspace; not Free or Go)

## Install

Copy the skill folder you want into your skills directory:

```bash
git clone https://github.com/Atipico1/awesome-chatgpt-sites.git
cp -R awesome-chatgpt-sites/skills/sites-issue-tracker ~/.codex/skills/
```

Then ask Codex, for example: "Build me an issue tracker on Sites."

## Adding a skill

- One app per skill: `skills/sites-<app>/SKILL.md`
- Put only instructions in the skill. Do not include app source code.
- Leave setup, build, and publishing to the official Sites skill. The app skill should cover product decisions and done criteria.
- If the app cannot run within Sites limits (Cloudflare Workers runtime, ChatGPT sign-in, D1/R2 storage), drop or scope down that feature.
