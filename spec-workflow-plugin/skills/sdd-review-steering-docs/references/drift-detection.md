# Project State Drift Detection

Detects when actual project state diverges from documentation.

## When to Use

- After adding/removing dependencies
- After introducing new tools or scripts
- After directory restructuring
- Before creating new specs
- Periodic maintenance

## Drift Detection Workflow

### Step 1: Identify Project State Sources

**Dependencies (tech.md drift)**

| Platform | Check Files |
|----------|-------------|
| Swift/iOS | `Package.swift`, `Package.resolved`, `Podfile` |
| Node.js | `package.json`, `package-lock.json` |
| Python | `requirements.txt`, `pyproject.toml` |
| Go | `go.mod`, `go.sum` |

**Tools (tech.md drift)**

| File | Extract |
|------|---------|
| `.nvmrc`, `.swift-version` | Runtime versions |
| `Scripts/`, `bin/` | Custom tools |
| `screwdriver.yaml`, `.github/workflows/` | CI/CD config |

**Structure (structure.md drift)**

| Method | Extract |
|--------|---------|
| `ls` on directories | Current structure |
| Compare to docs | New/removed/renamed dirs |

### Step 2: Compare Against Steering Docs

Use severity classifications from `validation-criteria.md` Drift Detection Criteria section.

**Programmatic check (dependencies):** Run `$SKILLS/sdd-common/scripts/util/detect-dependency-drift.py <tech.md> <manifest>` to compare documented dependencies against actual manifests (package.json, requirements.txt, etc.).

### Step 3: Generate Drift Report

Report sections (use markdown tables and status icons):
1. **Header**: project name, date
2. **Summary**: category (dependencies/tools/structure), drift count, severity
3. **Dependency Drift (tech.md)**: new, removed, and version-mismatched dependencies in separate tables, each with action column
4. **Structure Drift (structure.md)**: new directories and removed/renamed paths with action column
5. **Recommended Actions**: priority 1 (🔴 Critical) and priority 2 (🟡 Warning) checklists

### Step 4: User Confirmation

Present drift report, request confirmation for updates, offer to update steering docs for confirmed items.
