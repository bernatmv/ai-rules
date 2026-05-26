# Snapshot Conventions


## Contents

- [Storage Layout](#storage-layout)
- [Triggers](#triggers)
- [Snapshot JSON Format](#snapshot-json-format)
- [Metadata JSON Format](#metadata-json-format)
- [Comparison](#comparison)

## Storage Layout

Snapshots are stored alongside approvals:

```
.spec-workflow/approvals/{categoryName}/.snapshots/{fileName}/
├── metadata.json
├── snapshot-001.json
├── snapshot-002.json
└── ...
```

## Triggers

| Trigger | When Created |
|---------|-------------|
| `initial` | When approval is first requested |
| `revision_requested` | When status changes to needs_revision |
| `approved` | When status changes to approved |
| `manual` | When explicitly requested by user |

## Snapshot JSON Format

```json
{
  "id": "snapshot_<uuid>",
  "approvalId": "approval_xxx",
  "approvalTitle": "Requirements: user-auth",
  "version": 1,
  "timestamp": "2026-03-19T12:00:00Z",
  "trigger": "initial",
  "status": "pending",
  "content": "<full document content>",
  "fileStats": { "size": 2048, "lines": 64, "lastModified": "..." }
}
```

## Metadata JSON Format

```json
{
  "latestVersion": 3,
  "snapshots": [
    {"version": 1, "timestamp": "...", "trigger": "initial", "approvalId": "...", "snapshotFile": "snapshot-001.json"},
    {"version": 2, "timestamp": "...", "trigger": "revision_requested", ...},
    {"version": 3, "timestamp": "...", "trigger": "approved", ...}
  ]
}
```

## Comparison

Use `.spec-workflow/sdd spec/create-snapshot.py --compare` to diff two snapshot versions:
```
.spec-workflow/sdd spec/create-snapshot.py --compare --category-name "user-auth" --file-name "requirements.md" --snapshot-a 1 --snapshot-b 2
```
