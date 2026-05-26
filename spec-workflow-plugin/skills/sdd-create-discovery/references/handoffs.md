# sdd-create-discovery — Handoffs

Generated from `$SCRIPTS/handoff-registry.json`. Do not hand-edit;
run `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite` to regenerate.

| Script | Handoff | Command | Note |
|--------|---------|---------|------|
| `discovery/init-project.py` | `discovery/validate-manifest` | `.spec-workflow/sdd discovery/validate-manifest.py --name {ctx.target} --workspace {ctx.workspace}` | Validate the freshly-initialised manifest before adding artifacts. |
| `discovery/update-manifest.py` | `discovery/validate-manifest` | `.spec-workflow/sdd discovery/validate-manifest.py --name {ctx.target} --workspace {ctx.workspace}` | Validate the manifest after each mutation lands. |
| `discovery/validate-manifest.py` | `discovery/update-manifest` | `.spec-workflow/sdd discovery/update-manifest.py --name {ctx.target} --workspace {ctx.workspace} set-project-status --status approved` | Promote the project status once the manifest validates cleanly. |
