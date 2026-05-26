# Approval Modes

Detail reference for auto-detection, single-document mode, and override options. Referenced from `SKILL.md` § Approval Modes.

## Auto-Detection

At Step 1 (Pre-Flight), run the context detection script:

```
.spec-workflow/sdd spec/detect-context.py "{spec-name}" \
  [--workspace {path}]
```

| `context` | `approvalMode` | Meaning |
|-----------|---------------|---------|
| `coordination` | batch | Spec is a workspace coordination spec |
| `sub-spec` | batch | Spec is a workspace sub-spec delegation target |
| `standalone` | sequential | Regular single-repo spec |

The agent reads the `approvalMode` field and follows the corresponding flow.

## Single-Document Mode (Workspace Phase Loops)

When invoked from the workspace skill's phase loops (`phase-loop.md`),
the calling skill may direct the agent to execute a **single step** rather
than the full workflow. For example:

> Follow `$SKILLS/sdd-create-spec/SKILL.md` Step 3 (Write requirements.md)
> for spec `{subSpecName}` in `{repoPath}`. Skip Steps 4–10.

This is not a separate mode — the agent simply follows the specified step and
returns to the calling workflow. Approval is handled by the workspace phase
loop, not by this skill's approval gates.

## Single Document Request (Standalone)

When the user requests creation of a single document (e.g., "create requirements.md only"),
the agent executes the write step AND its corresponding approval step, then stops.
Step continuation applies within the write-approve pair.

| Request | Steps executed |
|---------|---------------|
| "requirements.md only" | Steps 1–4 (pre-flight, steering, write, approve) |
| "design.md only" | Steps 1–2, 5 (UI gate), 7–8 |
| "tasks.md only" | Steps 1–2, 9–10 |

## Override

Any calling skill can override the detected mode by instructing the agent:
- "Use **batch** approval mode for this spec" → forces batch regardless of context
- "Use **sequential** approval mode" → forces sequential regardless of context

The user can also override at the Pre-Flight prompt (e.g., "approve all docs at once").
