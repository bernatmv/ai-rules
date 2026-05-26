# Convention Review Criteria

Evaluates consistency with project conventions discovered from config files and sibling code.

## Contents
- [Discovery Protocol](#discovery-protocol)
- [Convention Checks](#convention-checks)

---

## Discovery Protocol

### Step 1: Check Config Files

Auto-detect ecosystem by checking for:

| Config File | Ecosystem |
|------------|-----------|
| `.eslintrc*`, `eslint.config.*` | JavaScript/TypeScript linting |
| `tsconfig.json` | TypeScript compilation |
| `.prettierrc*`, `prettier.config.*` | Code formatting |
| `.editorconfig` | Editor settings (indent, line endings) |
| `.shellcheckrc` | Shell script linting |
| `pyproject.toml`, `setup.cfg`, `.flake8` | Python tooling |
| `.swiftlint.yml` | Swift linting |
| `checkstyle.xml`, `.spotless` | Java formatting |
| `.rubocop.yml` | Ruby linting |
| `.golangci.yml` | Go linting |

### Step 2: Read Sibling Files

For each changed file:
1. Find 2-3 files of the same extension in the same directory
2. Extract patterns: naming convention, import ordering, file structure, export style
3. If no sibling files exist, look one directory up

### Step 3: Compare Changed Files

Compare changed files against discovered conventions from Steps 1-2.

---

## Convention Checks

| # | Check | Pass | Fail |
|---|-------|------|------|
| 1 | **Naming consistency** | Follows codebase convention (camelCase, snake_case, etc. as established) | Inconsistent with sibling file naming patterns |
| 2 | **Import ordering** | Same grouping and ordering as similar files in the project | Different ordering pattern than established files |
| 3 | **File structure** | Exports, type definitions, functions in same order as sibling files | Diverges from established structure in the directory |
| 4 | **Formatting compliance** | Follows `.prettierrc` / `.editorconfig` / linter config | Violates configured formatting rules |
| 5 | **Export style** | Matches project convention (default vs named, barrel files) | Inconsistent export pattern |

> Convention violations are typically Low severity unless the project has strict linting
> enforcement, in which case violations that would fail CI are Medium.
