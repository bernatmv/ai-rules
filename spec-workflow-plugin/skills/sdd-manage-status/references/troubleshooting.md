# Edge Cases

| Situation | Action |
|-----------|--------|
| `.spec-workflow/approvals/` missing or empty | Report "No pending approval requests found" and stop |
| Approval JSON file is empty (0 bytes) | Warn with file path, suggest user inspect or delete, skip |
| Malformed / corrupted JSON (parse failure) | Warn with file path and error, suggest user inspect or delete, skip |
| Missing `status` field in approval JSON | Warn that file shape is unexpected, skip |
| Unknown status value (e.g., `"in-review"`, `null`, typo) | Treat as already-resolved, warn with actual value, skip unless user overrides |
| Approval file not found | Report error, list available approvals |
| Status is already resolved (`approved`, `rejected`, etc.) | Warn user, skip unless they explicitly request override |
| Multiple specs match partial name | Ask user to clarify |
| Write failure (permissions, disk full) | Report error, read-back to check file integrity |
| Audit log write failure | Warn user but do not roll back the status change |
| Concurrent modification (Dashboard/VS Code edited between read and write) | Known limitation in single-user workflow; documented, low risk |

For common MCP and filesystem errors, see `$SKILLS/sdd-common/references/troubleshooting.md`.

## Script Error Messages

### "Status is 'approved', expected 'pending'"
**Cause:** Approval was already processed by a prior run or another agent.
**Resolution:** Verify the correct approval file. Run `.spec-workflow/sdd approval/list-pending.py` to find remaining pending ones.

### "JSON parse error skipped" or "Invalid JSON"
**Cause:** Approval file is corrupted, truncated, or empty.
**Resolution:** Inspect the file contents manually. Regenerate the approval request if needed.

### "Write verification failed — file may be corrupted"
**Cause:** Filesystem write was interrupted (disk full, permissions, concurrent access).
**Resolution:** Check disk space and file permissions. The original JSON content is logged in the audit entry's `previousContent` field for recovery.
