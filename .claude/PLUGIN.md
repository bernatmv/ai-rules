# Plugin list

Plugins in the `ai-rules` marketplace declare dependencies in each plugin's
`.claude-plugin/plugin.json`. Installing a plugin auto-installs its dependencies.

Third-party marketplaces are registered in `.claude/settings.json` via
`extraKnownMarketplaces` when you use this repo as a project. For a global install
outside this repo, add those marketplaces once:

```sh
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
/plugin marketplace add max-sixty/jean-claude
```

Then install the plugins you need:

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install core-plugin@ai-rules
/plugin install frontend-plugin@ai-rules
/plugin install devops-plugin@ai-rules
/reload-plugins
/mcp
```

Authenticate MCP-backed plugins after install:

```sh
/mcp
```

## core-plugin

Everyday engineering workflows, PR tooling, documents, and third-party productivity plugins.

### Official (`claude-plugins-official`)

| Plugin               | Provides                                                      |
| -------------------- | ------------------------------------------------------------- |
| `superpowers`        | Development workflows (TDD, planning, debugging, code review) |
| `code-review`        | PR and code review agents                                     |
| `code-simplifier`    | Code simplification workflows                                 |
| `github`             | GitHub MCP integration                                        |
| `ralph-loop`         | Autonomous iteration loop (`/ralph-loop`)                     |
| `atlassian`          | Jira and Confluence MCP integration                           |
| `gitlab`             | GitLab MCP integration                                        |
| `stripe`             | Stripe MCP integration                                        |
| `huggingface-skills` | Hugging Face Hub skills and MCP                               |
| `skill-creator`      | Create, evaluate, and improve agent skills                    |
| `notion`             | Notion MCP integration                                        |

### Third-party

| Plugin             | Marketplace                    | Add marketplace                                       |
| ------------------ | ------------------------------ | ----------------------------------------------------- |
| `document-skills`  | `anthropic-agent-skills`       | `/plugin marketplace add anthropics/skills`           |
| `claude-mem`       | `thedotmack`                   | `/plugin marketplace add thedotmack/claude-mem`       |
| `visual-explainer` | `visual-explainer-marketplace` | `/plugin marketplace add nicobailon/visual-explainer` |
| `jean-claude`      | `jean-claude`                  | `/plugin marketplace add max-sixty/jean-claude`       |

### MCP in core-plugin

| Server   | Notes                                       |
| -------- | ------------------------------------------- |
| `convex` | Convex backend MCP (`npx convex mcp start`) |

## frontend-plugin

Frontend design, browser testing, Figma, and UI debugging.

### Official (`claude-plugins-official`)

| Plugin                | Provides                              |
| --------------------- | ------------------------------------- |
| `frontend-design`     | Frontend UI design guidance           |
| `playwright`          | Playwright MCP for browser automation |
| `figma`               | Figma MCP and design workflow skills  |
| `chrome-devtools-mcp` | Chrome DevTools MCP                   |

### Third-party

| Plugin                | Marketplace                       | Add marketplace                                      |
| --------------------- | --------------------------------- | ---------------------------------------------------- |
| `web-asset-generator` | `web-asset-generator-marketplace` | `/plugin marketplace add alonw0/web-asset-generator` |

### MCP in frontend-plugin

| Server       | Notes                      |
| ------------ | -------------------------- |
| `astro-docs` | Astro documentation search |

## devops-plugin

Cloud deployment and backend infrastructure.

### Official (`claude-plugins-official`)

| Plugin     | Provides                 |
| ---------- | ------------------------ |
| `supabase` | Supabase MCP integration |
| `vercel`   | Vercel MCP integration   |

Manual install of any official dependency (without ai-rules plugins):

```sh
/plugin install <plugin-name>@claude-plugins-official
```

### Web asset generator

Favicons, app icons, and social sharing images (via `frontend-plugin` → `web-asset-generator`).

### Document skills

Excel, Word, PowerPoint, and PDF processing (via `core-plugin` → `document-skills`; includes the `pdf` skill).

### Claude MEM

Persistent memory across sessions (via `core-plugin` → `claude-mem`). Data lives in `~/.claude-mem`.

Alternative install:

```sh
npx claude-mem install
```

### Visual explainer

HTML diagrams, diff reviews, and plan reviews (via `core-plugin` → `visual-explainer`). Examples:

> draw a diagram of our authentication flow
> /diff-review
> /plan-review ~/docs/refactor-plan.md

### Google Workspace (Gmail, Drive, Calendar)

Provided by `core-plugin` → `jean-claude` — a skill/CLI plugin, not an MCP server.
Requires [uv](https://docs.astral.sh/uv/) (Python 3.11+).

After install, authenticate once:

```
Set up Google authentication for jean-claude
```

Or manually from the installed plugin directory:

```sh
uv run jean-claude auth
uv run jean-claude status
```

Credentials are stored in `~/.config/jean-claude/token.json`. You may see Google's
"unverified app" warning — use Advanced → Continue to proceed.

Example prompts:

```
Check my inbox for unread emails
Search Drive for quarterly reports
What's on my calendar today?
```

Also includes iMessage on macOS (optional).

## Ralph Wiggum

Provided by `core-plugin` → `ralph-loop`. Usage:

`/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"`

Example:

`/ralph-loop "Build a REST API for todos. Requirements: CRUD operations, input validation, tests. Output <promise>COMPLETE</promise> when done." --completion-promise "COMPLETE" --max-iterations 50`

Cancel with `/cancel-ralph`.

Good task definitions:

```
Build a REST API for todos.

When complete:
- All CRUD endpoints working
- Input validation in place
- Tests passing (coverage > 80%)
- README with API docs
- Output: <promise>COMPLETE</promise>
```

```
Phase 1: User authentication (JWT, tests)
Phase 2: Product catalog (list/search, tests)
Phase 3: Shopping cart (add/remove, tests)

Output <promise>COMPLETE</promise> when all phases done.
```

```
Implement feature X following TDD:
1. Write failing tests
2. Implement feature
3. Run tests
4. If any fail, debug and fix
5. Refactor if needed
6. Repeat until all green
7. Output: <promise>COMPLETE</promise>
```

## Manage dependencies

List installed plugins and dependency errors:

```sh
claude plugin list
/plugin
```

Remove orphaned auto-installed dependencies:

```sh
claude plugin prune
```

Uninstall a plugin and clean up its dependencies:

```sh
claude plugin uninstall core-plugin@ai-rules --prune
claude plugin uninstall frontend-plugin@ai-rules --prune
claude plugin uninstall devops-plugin@ai-rules --prune
```
