# Location

`~/.claude/skills/`

# Add marketplaces

```sh
/plugin marketplace add anthropics/skills
```

# Skills list

## Frontend design

`npx skills add anthropics/claude-code - skill frontend-design`

## PDF

`npx skills add anthropics/claude-code - skill pdf`

## Skill creator

`npx skills add anthropics/claude-code - skill skill-creator`

## Web artifacts builder

`npx skills add anthropics/claude-code - skill web-artifacts-builder`

## Web asset generator

`npx skills add anthropics/claude-code - skill web-asset-generator`

## Webapp testing

`npx skills add anthropics/claude-code - skill webapp-testing`

## Browser use

`npx skills add https://github.com/browser-use/browser-use --skill browser-use`

## Code Reviewer

`npx claude-code-templates@latest --skill development/code-reviewer`

## Remotion

`npx skills add remotion/agent-skills`

Then in Claude:

```sh
/remotion Create a 30-second product demo video showing our API
dashboard with animated charts and transitions
```

## Excalidraw

`npx skills add https://github.com/coleam00/excalidraw-diagram-skill --skill excalidraw-diagram`

## Shadcn

`npx skills add shadcn/ui`

## Vercel skills

`npx skills add vercel-labs/agent-skills`

## Next best practices

`npx skills add https://github.com/vercel-labs/next-skills --skill next-best-practices`

## Create screenshots for app

`npx skills add ParthJadhav/app-store-screenshots`

> Build App Store screenshots
> Generate marketing screenshots for an iOS app
> Create exportable screenshot assets

## Visual explainer

```sh
/plugin marketplace add nicobailon/visual-explainer
/plugin install visual-explainer@visual-explainer-marketplace
```

> draw a diagram of our authentication flow
> /diff-review
> /plan-review ~/docs/refactor-plan.md

## Claude MEM

`npx claude-mem install`

_OR_

```sh
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem
```

Located in:

`~/.claude-mem`

## Ralph Wiggum

```sh
/plugin install anthropic@ralph-loop
```

Usage:

`/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"`

eg:

`/ralph-loop "Build a REST API for todos. Requirements: CRUD operations, input validation, tests. Output <promise>COMPLETE</promise> when done." --completion-promise "COMPLETE" --max-iterations 50`

`/cancel-ralph`

Good definitions:

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
