# Path Conventions

Cross-skill file references in SDD skills use the `$SKILLS/` prefix to ensure
depth-independent, stable resolution. This document defines the convention
and resolution rules.

## Contents

- [Prefix Reference](#prefix-reference)
- [Examples](#examples)
  - [Cross-skill (any file, any depth)](#cross-skill-any-file-any-depth)
  - [Within-skill (from SKILL.md)](#within-skill-from-skillmd)
  - [Consumer-relative (shared template)](#consumer-relative-shared-template)
  - [Within sdd-common (references → scripts)](#within-sdd-common-references--scripts)
- [Resolution Rules](#resolution-rules)
- [IDE Mappings](#ide-mappings)
- [Dependency Tables](#dependency-tables)
- [Script Name References in Prose](#script-name-references-in-prose)
- [Adding New Files](#adding-new-files)
- [Moving Files](#moving-files)

## Prefix Reference

| Prefix | Resolves to | When to use |
|--------|-------------|-------------|
| `$SKILLS/` | IDE skills directory (see [IDE Mappings](#ide-mappings)) | Any cross-skill reference |
| `$SCRIPTS/` | `$SKILLS/sdd-common/scripts/` | Script file references (shorter alias) |
| `.spec-workflow/sdd` | IDE-independent script runner shim (no PYTHONPATH needed) | Script invocations (`.spec-workflow/sdd group/script.py args...`) |
| `references/` | Same skill's `references/` directory | Within-skill from SKILL.md |
| `@consumer/` | Consuming skill's root directory | Shared templates (e.g., review-workflow-base.md) |
| `../scripts/` | Parent directory relative to file | Within sdd-common (references → scripts) |
| (bare filename) | Same directory as the containing file | Co-located files |

## Examples

### Cross-skill (any file, any depth)

```
$SKILLS/sdd-common/references/approval-flow.md
$SKILLS/sdd-common/scripts/spec/check-status.py
$SKILLS/sdd-implement-spec/SKILL.md
```

### Within-skill (from SKILL.md)

```
references/spec-workflow.md
references/triage-criteria.md
```

### Consumer-relative (shared template)

Used in `sdd-common/references/review-workflow-base.md` for paths that resolve
in the consuming skill's directory:

```
@consumer/references/cross-validation-criteria.md
```

### Within sdd-common (references → scripts)

Files in `sdd-common/references/` that reference sibling scripts:

```
../scripts/approval/request.py
../scripts/util/generate-prompt.py
```

## Resolution Rules

1. **`$SKILLS/path`** → `{workspace_root}/{ide_skills_dir}/path`
2. **`$SCRIPTS/path`** → `{workspace_root}/{ide_skills_dir}/sdd-common/scripts/path`
3. **`.spec-workflow/sdd script.py`** → IDE-independent shim that resolves `{workspace_root}/{ide_skills_dir}/sdd-common/scripts/{script}.py` <!-- noverify -->
4. **`@consumer/path`** → `{consuming_skill_root}/path` (validated by the
   consuming skill, not the defining file)
5. **`references/path`** → `{current_skill_root}/references/path`
6. **`../scripts/path`** → Relative to file location (within-skill only)
7. **Bare `filename.md`** → Same directory as the containing file

## IDE Mappings

`$SKILLS/` resolves based on the active IDE. The first existing directory wins.

| IDE | Skills directory | Detection |
|-----|-----------------|-----------|
| Cursor | `.cursor/skills/` | Directory exists check |
| Claude Code | `.claude/skills/` | Directory exists check |
| Override | `$SDD_SKILLS_ROOT` env var | Environment variable |

Scripts detect the correct directory automatically via
`sdd_core.paths.find_skills_root()`. In documentation, always use the
`$SKILLS/` prefix — never write a literal IDE-specific path.

## Dependency Tables

Each SKILL.md declares cross-skill file dependencies in its `## Dependencies`
table using `$SKILLS/` paths. When a file moves, update one table row per
consuming skill instead of searching through prose.

## Script Name References in Prose

Scripts in `sdd-common/scripts/` are organized into subdirectories:
`approval/`, `review/`, `spec/`, `util/`, `workspace/`. Always use the
grouped path — never bare flat names.

| Context | Format | Example |
|---------|--------|---------|
| Script invocation (preferred) | `.spec-workflow/sdd {group}/{script}.py` | `.spec-workflow/sdd spec/check-status.py --target "user-auth"` |
| Script invocation (cross-repo) | `.spec-workflow/sdd --project {path} {group}/{script}.py` | `.spec-workflow/sdd --project /path/to/repo spec/check-status.py --all` |
| Cross-skill file reference | `$SKILLS/sdd-common/scripts/{group}/{script}.py` | `$SKILLS/sdd-common/scripts/spec/check-status.py` |
| Within sdd-common (SKILL.md → scripts) | `scripts/{group}/{script}.py` | `scripts/approval/request.py` | <!-- noverify -->
| Within sdd-common (references → scripts) | `../scripts/{group}/{script}.py` | `../scripts/review/count-effective-lines.py` |
| Bare filename | Same directory as containing file only | `registry.py` (from within `review_quality/`) |

**Never use** flat phantom names (e.g., init-workspace.py, request-approval.py). <!-- noverify -->
These do not exist on disk.

## Adding New Files

1. Create the file in the appropriate skill's directory
2. Add to the skill's `files` list in `skills-registry.json`
3. If it's a shared resource in sdd-common, add to `publishedResources`
4. Add `$SKILLS/` references in consuming skills' dependency tables
5. Add to `externalDependencies` in consuming skills' registry entries

## Moving Files

1. Update the file's location on disk
2. Update `skills-registry.json` (`files`, `publishedResources`)
3. Update `$SKILLS/` paths in all consuming files
4. Update `externalDependencies` in consuming skills' registry entries
