# sdd-workspace-create-spec — Handoffs

Generated from `$SCRIPTS/handoff-registry.json`. Do not hand-edit;
run `.spec-workflow/sdd internal_lints/skill_md_handoff_table.py --rewrite` to regenerate.

| Script | Handoff | Command | Note |
|--------|---------|---------|------|
| `workspace/advance-phase.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --target {ctx.target} --phase launch` | Launch the review pipeline for the new currentPhase. |
| `workspace/advance-phase.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Confirm the phase advance landed in the tracker. |
| `workspace/batch-approve.py` | `workspace/confirm-batch-approval` | `.spec-workflow/sdd workspace/confirm-batch-approval.py --workspace {ctx.workspace} --target {ctx.target}` | After user consents, confirm the batch presented above. |
| `workspace/check-health.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Read tracker state once the workspace is healthy. |
| `workspace/check-spec-shape.py` | `workspace/update-tracker` | `.spec-workflow/sdd workspace/update-tracker.py --workspace {ctx.workspace} --target {ctx.target_with_repo} --phase {ctx.phase} --doc-status reviewed` | Mark the validated sub-spec doc as reviewed. |
| `workspace/check-spec-shape.py` | `workspace/phase-approve` | `.spec-workflow/sdd workspace/phase-approve.py --workspace {ctx.workspace} --target {ctx.target} --doc {ctx.phase}` | Run phase-approve once every active repo reports reviewed. |
| `workspace/check-status.py` | `workspace/phase-status` | `.spec-workflow/sdd workspace/phase-status.py --workspace {ctx.workspace} --target {ctx.target}` | Drill into per-repo docStatus for the current phase. |
| `workspace/confirm-batch-approval.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Confirm the batch approval landed in the tracker. |
| `workspace/ensure-healthy.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Read tracker state once pre-flight passes. |
| `workspace/extract-delegation.py` | `workspace/check-spec-shape` | `.spec-workflow/sdd workspace/check-spec-shape.py --workspace {ctx.workspace} --target {ctx.target_with_repo}` | Validate the sub-spec docs once authored from the delegation context. |
| `workspace/init-feature.py` | `workspace/update-manifest:set-repo-role` | `.spec-workflow/sdd workspace/update-manifest.py --workspace {ctx.workspace} --target {ctx.target} set-repo-role --repo-id <repo-id> --role "<short repo-purpose description>"` | Populate the free-form role on each repo flagged with manifest-role-unset. |
| `workspace/init-feature.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Confirm the feature bootstrap landed in the tracker. |
| `workspace/init.py` | `workspace/init-feature` | `.spec-workflow/sdd workspace/init-feature.py --workspace {ctx.workspace} --target <feature> --repo coordinator:{ctx.workspace}:<sub-spec>` | Bootstrap a workspace feature once the workspace is initialised. |
| `workspace/phase-approve.py` | `review/pipeline-tick:launch` | `.spec-workflow/sdd review/pipeline-tick.py --workspace {ctx.workspace} --target {ctx.target} --phase launch` | Open the next phase's review pipeline once approval lands. |
| `workspace/phase-approve.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Confirm tracker advanced to the next currentPhase. |
| `workspace/phase-status.py` | `workspace/phase-approve` | `.spec-workflow/sdd workspace/phase-approve.py --workspace {ctx.workspace} --target {ctx.target} --doc {ctx.phase}` | Approve the current doc once every repo reports reviewed. |
| `workspace/preflight-all.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Read coordination tracker state across the fan-out. |
| `workspace/reconcile-tracker.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Confirm the reconciled summary. |
| `workspace/resolve-advisory.py` | `workspace/resolve-advisory:mark-resolved` | `.spec-workflow/sdd workspace/resolve-advisory.py --workspace {ctx.workspace} --name <advisory-name>` | Mark a workspace advisory resolved for the current session. |
| `workspace/retroactive-review.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Verify retroactive stamps landed in the tracker. |
| `workspace/set-doc-approval.py` | `workspace/phase-approve` | `.spec-workflow/sdd workspace/phase-approve.py --workspace {ctx.workspace} --target {ctx.target} --doc {ctx.phase}` | Advance the phase once every repo has approval recorded. |
| `workspace/sync-skills-pack.py` | `workspace/sync-skills-pack:rotate` | `.spec-workflow/sdd workspace/sync-skills-pack.py --target "{ctx.target}" --workspace {ctx.workspace}` | Rotate workspace-shared reference docs from the coordinator to every target repo. |
| `workspace/update-manifest.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Verify the manifest write took effect. |
| `workspace/update-tracker.py` | `workspace/check-status` | `.spec-workflow/sdd workspace/check-status.py --workspace {ctx.workspace} --target {ctx.target}` | Verify the tracker write took effect. |
