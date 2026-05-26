# Plugin list

`core-plugin@ai-rules` declares all plugins below as dependencies in
`core-plugin/.claude-plugin/plugin.json`. Installing core-plugin auto-installs them.

Third-party marketplaces are registered in `.claude/settings.json` via
`extraKnownMarketplaces` when you use this repo as a project. For a global install
outside this repo, add those marketplaces once:

```sh
/plugin marketplace add alonw0/web-asset-generator
/plugin marketplace add anthropics/skills
/plugin marketplace add thedotmack/claude-mem
/plugin marketplace add nicobailon/visual-explainer
```

Then install core-plugin:

```sh
/plugin marketplace add bernatmv/ai-rules
/plugin install core-plugin@ai-rules
/reload-plugins
```

Authenticate MCP-backed plugins after install:

```sh
/mcp
```

## Official (`claude-plugins-official`)

Auto-installed as dependencies of `core-plugin`:

| Plugin | Provides |
| --- | --- |
| `frontend-design` | Frontend UI design guidance |
| `superpowers` | Development workflows (TDD, planning, debugging, code review) |
| `code-review` | PR and code review agents |
| `code-simplifier` | Code simplification workflows |
| `github` | GitHub MCP integration |
| `playwright` | Playwright MCP for browser automation |
| `ralph-loop` | Autonomous iteration loop (`/ralph-loop`) |
| `figma` | Figma MCP integration |
| `supabase` | Supabase MCP integration |
| `atlassian` | Jira and Confluence MCP integration |
| `vercel` | Vercel MCP integration |
| `gitlab` | GitLab MCP integration |
| `chrome-devtools-mcp` | Chrome DevTools MCP |
| `stripe` | Stripe MCP integration |
| `huggingface-skills` | Hugging Face Hub skills and MCP |
| `skill-creator` | Create, evaluate, and improve agent skills |
| `notion` | Notion MCP integration |

Manual install (if not using core-plugin):

```sh
/plugin install <plugin-name>@claude-plugins-official
```

## Third-party (auto-installed with core-plugin)

| Plugin | Marketplace | Add marketplace |
| --- | --- | --- |
| `web-asset-generator` | `web-asset-generator-marketplace` | `/plugin marketplace add alonw0/web-asset-generator` |
| `document-skills` | `anthropic-agent-skills` | `/plugin marketplace add anthropics/skills` |
| `claude-mem` | `thedotmack` | `/plugin marketplace add thedotmack/claude-mem` |
| `visual-explainer` | `visual-explainer-marketplace` | `/plugin marketplace add nicobailon/visual-explainer` |

### Web asset generator

Favicons, app icons, and social sharing images.

### Document skills

Excel, Word, PowerPoint, and PDF processing from Anthropic's example skills catalog (includes the `pdf` skill).

### Claude MEM

Persistent memory across sessions. Data lives in `~/.claude-mem`.

Alternative install:

```sh
npx claude-mem install
```

### Visual explainer

HTML diagrams, diff reviews, and plan reviews. Examples:

> draw a diagram of our authentication flow
> /diff-review
> /plan-review ~/docs/refactor-plan.md

## Ralph Wiggum

Provided by the `ralph-loop` dependency. Usage:

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

Uninstall core-plugin and clean up its dependencies:

```sh
claude plugin uninstall core-plugin@ai-rules --prune
```
