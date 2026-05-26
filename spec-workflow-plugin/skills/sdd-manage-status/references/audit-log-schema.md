# Audit Log Schema

Append one JSON line per status change to `.spec-workflow/approval-audit.log` (JSONL format):

```json
{
  "timestamp": "2026-02-22T10:30:00.000Z",
  "type": "approval-status-change",
  "actor": "ai-agent",
  "approvalId": "approval_1708600000_abc",
  "title": "Review requirements.md",
  "filePath": ".spec-workflow/specs/user-auth/requirements.md",
  "category": "spec",
  "categoryName": "user-auth",
  "document": "requirements.md",
  "previousStatus": "pending",
  "newStatus": "approved",
  "response": "All review criteria met - PASS score",
  "previousContent": { },
  "metadata": {
    "skillVersion": "1.3.0",
    "triggerContext": "post-review-approval"
  }
}
```

## Field Reference

- `type`: `"approval-status-change"` for normal transitions, `"approval-status-override"` for non-pending overrides
- `actor`: Resolved dynamically per the **Actor Detection** section in SKILL.md (default: `"ai-agent"`)
- `title`: from the approval JSON's `title` field
- `filePath`: from the approval JSON's `filePath` field (enables cross-referencing with MCP data)
- `document`: basename of `filePath` for readability
- `previousContent`: full approval JSON before modification (conforms to `ApprovalRequest`; enables manual recovery)
- `metadata.skillVersion`: from this skill's frontmatter `version` field
- `metadata.triggerContext`: one of `"post-review-approval"`, `"manual-status-change"`, `"batch-approval"`, `"status-override"`

## Rules

- If the audit log file does not exist, create it. Append only — never overwrite.
- **Audit write is best-effort**: if the status change succeeded but the audit append fails, warn the user but do not roll back the status change.
