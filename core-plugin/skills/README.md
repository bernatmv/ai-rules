# Skills

Agentic skills that extend Claude's capabilities with reusable, composable instructions. Skills follow the [Agent Skills](https://agentskills.io/specification) open standard and can include custom slash commands, scripts, reference material, and templates.

## How Skills Work

Skills are self-contained instruction sets that Claude uses when relevant. They follow a **progressive disclosure** pattern:

1. **Metadata** (~100 tokens) - `name` and `description` are loaded at startup for all skills
2. **Instructions** (< 5000 tokens recommended) - full `SKILL.md` body loads when the skill is activated
3. **Resources** (as needed) - supporting files (`scripts/`, `references/`, `assets/`) load only when required

This keeps the context window lean while giving Claude deep capabilities on demand.

## Directory Structure

Each skill is a directory containing at minimum a `SKILL.md` file:

```
skills/
├── README.md
├── code-review/
│   ├── SKILL.md              # Required: main instructions
│   ├── references/
│   │   └── CHECKLIST.md      # Detailed review checklist
│   └── scripts/
│       └── lint-check.sh     # Script Claude can execute
├── deploy/
│   ├── SKILL.md
│   └── scripts/
│       └── deploy.sh
├── fix-issue/
│   └── SKILL.md
└── api-conventions/
    ├── SKILL.md
    └── references/
        ├── error-codes.md
        └── endpoint-patterns.md
```

## SKILL.md Format

Every skill requires a `SKILL.md` file with YAML frontmatter and Markdown instructions.

### Minimal Example

```yaml
---
name: code-review
description: Reviews code for quality, security, and best practices. Use after making code changes or when the user asks for a review.
---

When reviewing code:

1. Check for correctness and potential bugs
2. Evaluate error handling
3. Look for security vulnerabilities
4. Assess readability and maintainability
5. Suggest specific improvements with code examples
```

### Full Example with All Options

```yaml
---
name: deploy
description: Deploy the application to production with safety checks. Use when the user wants to deploy or release code.
license: Apache-2.0
compatibility: Requires git, docker, and access to the internet
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash(git *) Bash(docker *) Read
context: fork
agent: general-purpose
model: sonnet
argument-hint: "[environment]"
metadata:
  author: platform-team
  version: "2.0"
---

Deploy the application to $ARGUMENTS (default: staging).

## Pre-deployment checks
1. Run the full test suite
2. Verify no uncommitted changes
3. Check that the branch is up to date with main

## Deployment steps
1. Build the Docker image with the current git SHA as tag
2. Push the image to the container registry
3. Update the deployment manifest
4. Apply the deployment
5. Wait for rollout to complete
6. Run smoke tests against the deployed environment

## Rollback
If smoke tests fail, immediately roll back to the previous version.

## Supporting resources
- See [references/runbook.md](references/runbook.md) for detailed runbook
```

## Frontmatter Reference

### Required by Agent Skills Spec

| Field         | Required | Constraints                                                                      |
| ------------- | -------- | -------------------------------------------------------------------------------- |
| `name`        | Yes      | 1-64 chars. Lowercase letters, numbers, hyphens only. Must match directory name. |
| `description` | Yes      | 1-1024 chars. Describes what the skill does and when to use it.                  |

### Optional (Agent Skills Spec)

| Field           | Description                                                  |
| --------------- | ------------------------------------------------------------ |
| `license`       | License name or reference to a bundled license file          |
| `compatibility` | Environment requirements (max 500 chars)                     |
| `metadata`      | Arbitrary key-value mapping for additional metadata          |
| `allowed-tools` | Space-delimited list of pre-approved tools the skill may use |

### Claude Code Extensions

| Field                      | Description                                                                      |
| -------------------------- | -------------------------------------------------------------------------------- |
| `disable-model-invocation` | `true` to prevent Claude from auto-loading this skill (manual `/name` only)      |
| `user-invocable`           | `false` to hide from the `/` menu (Claude-only background knowledge)             |
| `context`                  | `fork` to run in an isolated subagent context                                    |
| `agent`                    | Subagent type when `context: fork` is set (`Explore`, `Plan`, `general-purpose`) |
| `model`                    | Model to use when this skill is active                                           |
| `argument-hint`            | Hint shown during autocomplete (e.g., `[issue-number]`)                          |
| `hooks`                    | Lifecycle hooks scoped to this skill                                             |

### Name Validation Rules

- Lowercase letters, numbers, and hyphens only (`a-z`, `0-9`, `-`)
- Must not start or end with a hyphen
- Must not contain consecutive hyphens (`--`)
- Must match the parent directory name

```yaml
# Valid
name: code-review
name: data-analysis
name: fix-issue

# Invalid
name: Code-Review      # uppercase not allowed
name: -code-review     # starts with hyphen
name: code--review     # consecutive hyphens
```

## Invocation Control

| Configuration                    | User can invoke | Claude can invoke | When loaded into context               |
| -------------------------------- | --------------- | ----------------- | -------------------------------------- |
| (default)                        | Yes             | Yes               | Description at startup, full on invoke |
| `disable-model-invocation: true` | Yes             | No                | Only when user invokes with `/name`    |
| `user-invocable: false`          | No              | Yes               | Description at startup, full on invoke |

## String Substitutions

Skills support dynamic values in content:

| Variable               | Description                                  |
| ---------------------- | -------------------------------------------- |
| `$ARGUMENTS`           | All arguments passed when invoking the skill |
| `$ARGUMENTS[N]`        | Specific argument by 0-based index           |
| `$N`                   | Shorthand for `$ARGUMENTS[N]`                |
| `${CLAUDE_SESSION_ID}` | Current session ID                           |

### Example with Arguments

```yaml
---
name: fix-issue
description: Fix a GitHub issue by number
disable-model-invocation: true
argument-hint: "[issue-number]"
---

Fix GitHub issue #$ARGUMENTS following our coding standards.

1. Read the issue description using `gh issue view $ARGUMENTS`
2. Understand the requirements
3. Implement the fix
4. Write tests
5. Create a commit referencing the issue
```

Usage: `/fix-issue 123`

### Dynamic Context Injection

Use `` !`command` `` to inject shell command output into the skill:

```yaml
---
name: pr-summary
description: Summarize changes in a pull request
context: fork
agent: Explore
---

## Pull request context
- PR diff: !`gh pr diff`
- PR comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

## Task
Summarize this pull request with key changes and potential concerns.
```

## Optional Directories

### scripts/

Executable code that agents can run:

```
scripts/
├── deploy.sh          # Deployment automation
├── validate.py        # Input validation
└── generate-docs.sh   # Documentation generation
```

Scripts should be self-contained, include helpful error messages, and handle edge cases.

### references/

Additional documentation loaded on demand:

```
references/
├── REFERENCE.md       # Detailed technical reference
├── error-codes.md     # Complete error code listing
└── api-patterns.md    # API design patterns
```

Keep individual reference files focused. Agents load these on demand, so smaller files mean less context usage.

### assets/

Static resources:

```
assets/
├── template.json      # Configuration templates
├── schema.json        # Data schemas
└── example-output.md  # Example outputs
```

## Skill Examples

### API Conventions (Background Knowledge)

````yaml
---
name: api-conventions
description: API design patterns and conventions for this codebase. Loaded when implementing or modifying API endpoints.
user-invocable: false
---

When writing API endpoints:

## URL patterns
- Use plural nouns: `/users`, `/orders`
- Use kebab-case: `/user-profiles`
- Nest for relationships: `/users/{id}/orders`

## Response format
All responses use this envelope:
```json
{
  "data": {},
  "meta": { "request_id": "..." },
  "errors": []
}
````

## Error handling

- Use standard HTTP status codes
- Include machine-readable error codes
- For details, see [references/error-codes.md](references/error-codes.md)

````

### Commit Skill (User-Only)

```yaml
---
name: commit
description: Create a well-formatted git commit
disable-model-invocation: true
allowed-tools: Bash(git *)
---

Create a commit for the current changes:

1. Run `git status` and `git diff --staged` to see what's being committed
2. If nothing is staged, stage relevant files (ask the user if unclear)
3. Write a commit message following conventional commits:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `refactor:` for refactoring
   - `docs:` for documentation
   - `test:` for tests
   - `chore:` for maintenance
4. Keep the subject line under 72 characters
5. Add a body if the change needs explanation
````

### Deep Research (Forked Context)

```yaml
---
name: deep-research
description: Research a topic thoroughly across the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:

1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Trace data flow and dependencies
4. Summarize findings with specific file references and line numbers
```

## Skill Locations and Priority

| Priority | Location                           | Scope                     |
| -------- | ---------------------------------- | ------------------------- |
| Highest  | Enterprise managed settings        | All users in organization |
| High     | `~/.claude/skills/<name>/SKILL.md` | All your projects         |
| Medium   | `.claude/skills/<name>/SKILL.md`   | Current project only      |
| Low      | Plugin `skills/<name>/SKILL.md`    | Where plugin is enabled   |

## Validation

Use the [skills-ref](https://github.com/agentskills/agentskills/tree/main/skills-ref) library to validate skills:

```bash
skills-ref validate ./my-skill
```

## Best Practices

1. **Keep `SKILL.md` under 500 lines** - move detailed reference material to separate files
2. **Write descriptive `description` fields** - include keywords that help Claude match tasks to skills
3. **Use `disable-model-invocation: true`** for skills with side effects (deploy, commit, send messages)
4. **Use `user-invocable: false`** for background knowledge that isn't actionable as a command
5. **Use `context: fork`** for tasks that produce verbose output or need isolation
6. **Keep file references one level deep** - avoid deeply nested reference chains
7. **Use progressive disclosure** - metadata at startup, instructions on invoke, resources when needed
8. **Check into version control** - share project skills with your team
