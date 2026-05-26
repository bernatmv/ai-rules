# fullstack-plugin

One-install bundle for the full `ai-rules` stack. Installing `fullstack-plugin@ai-rules` auto-installs:

| Plugin | Provides |
| --- | --- |
| `core-plugin` | Engineering workflows, GitHub/Jira/Notion, documents, Google Workspace, productivity plugins |
| `frontend-plugin` | Frontend design, Figma, Playwright, Chrome DevTools, web assets, marketing copy & SEO, Astro docs MCP |
| `devops-plugin` | Supabase and Vercel MCP integrations |

## Install

```sh
# Third-party marketplaces required by core-plugin and frontend-plugin (one-time)
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude
/plugin marketplace add coreyhaines31/marketingskills

/plugin marketplace add bernatmv/ai-rules
/plugin install fullstack-plugin@ai-rules
/reload-plugins
/mcp
```

Install individual plugins instead when you only need part of the stack — see the [root README](../README.md).
