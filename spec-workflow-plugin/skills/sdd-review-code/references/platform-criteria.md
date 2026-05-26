# Platform-Specific Criteria

Loaded conditionally when the project's `tech.md` documents platform-specific
patterns, conventions, or constraints.

## How to Apply

Do **not** use hardcoded platform rules. Instead, derive all platform-specific
checks from the project's steering documents:

1. **Read `tech.md`** for:
   - Language/framework conventions (naming, architecture patterns, concurrency model)
   - Security patterns (credential storage, auth flows)
   - Error handling expectations (force unwrap rules, exception patterns)
   - Memory management patterns (reference counting, GC, ownership)

2. **Read `structure.md`** for:
   - File naming conventions (casing, suffixes, extensions)
   - Test file location and naming patterns
   - Module/directory organization rules

3. **Build a checklist** from what those docs specify and evaluate the implementation
   against it. If `tech.md` and `structure.md` don't specify a convention, do not
   invent one — mark it ➖ N/A.

## Evaluation Table

| Area | Source | Check |
|------|--------|-------|
| File naming | structure.md | Files follow documented naming conventions |
| Architecture pattern | tech.md | Implementation uses the documented pattern (e.g., the pattern named in tech.md, not a different one) |
| Concurrency model | tech.md | Async patterns match documented approach |
| Security | tech.md | Credential storage and auth follow documented patterns |
| Memory management | tech.md | Follows documented ownership/lifecycle patterns |
| Testing conventions | structure.md | Test files at documented locations with documented naming |
