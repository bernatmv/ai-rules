# PRD Edge Cases

See `$SKILLS/sdd-common/references/common-edge-cases.md` for shared patterns
(Template Missing, Approval Rejected, Resume Existing, Project/Resource Already
Exists). Skill-specific edge cases:

| Situation | Action |
|-----------|--------|
| User provides pre-written problem statement | Switch to pressure-test mode (skip exploratory questions) |
| User wants to skip steps | Explain readiness gate rationale; allow skip with explicit acknowledgment |
| NFR left as TBD | Require resolution plan (owner + date); block if TBD for financially material data |
| User says "I don't know" to a question | Record as open question with Blocks entry |
| PRD session surfaces steering doc updates | Capture in Step 8 before session closes |
| User wants spec immediately after PRD | Handoff to sdd-create-spec with {prd-name} as context |
| Discovery project has other PRDs | List existing PRD artifacts from manifest. Proceed with new {prd-name}. |
| User doesn't specify PRD name | Default to `prd.md`. |
| PRD name doesn't contain `prd` | Warn: "Filename should contain 'prd' for auto-detection. Proceeding, but type will be 'supplementary' in manifest." |
| validate-prd.py finds issues after generation | Fix → re-validate loop (max 2 cycles) |
| Update to {prd-name} with existing approved spec | Warn: "Spec was approved against the previous PRD. Consider reviewing spec alignment." |
