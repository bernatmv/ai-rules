# sdd-create-prd — Handoffs

Generated from `$SCRIPTS/handoff-registry.json`. Do not hand-edit;
run `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite` to regenerate.

| Script | Handoff | Command | Note |
|--------|---------|---------|------|
| `prd/validate-prd.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --category discovery --target-name {ctx.target} --phase launch --doc prd` | Run the review pipeline once the PRD passes structural validation. |
| `prd/validate-readiness.py` | `prd/validate-prd` | `.spec-workflow/sdd prd/validate-prd.py .spec-workflow/discovery/{ctx.target}/prd.md` | Run the structural PRD lint once the readiness gate passes. |
| `prd/write-session-state.py` | `prd/validate-readiness` | `.spec-workflow/sdd prd/validate-readiness.py --target {ctx.target} --gate pre-requirements --session-file --workspace {ctx.workspace}` | Re-check the readiness gate after each session step lands. |
