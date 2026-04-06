# Plugin list

## Install

```sh
claude
/plugin
# select from list
frontend-design
* superpowers
code-review
code-simplifier
github
playwright
ralph-loop
figma
supabase
* atlassian
vercel
* gitlab
chrome-devtools-mcp
* stripe
* huggingface-skills
notion
```

## Web asset generator

```sh
/plugins marketplace add alonw0/web-asset-generator
/plugin install web-asset-generator@web-asset-generator-marketplace
```

## Document skills

```sh
/plugin marketplace add anthropics/skills
/plugin
# look for pdf or document skills
```

## Claude MEM

```sh
npx claude-mem install
```

_OR_

```sh
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem
```

Located in:

`~/.claude-mem`

## Visual explainer

```sh
/plugin marketplace add nicobailon/visual-explainer
/plugin install visual-explainer@visual-explainer-marketplace
```

> draw a diagram of our authentication flow
> /diff-review
> /plan-review ~/docs/refactor-plan.md

## Ralph Wiggum

```sh
/plugin install anthropic@ralph-loop # or installed through /plugin above
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
