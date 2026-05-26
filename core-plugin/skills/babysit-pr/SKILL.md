---
description: Autonomous PR babysitter — fix merge conflicts, address review feedback, and resolve build failures with built-in recurring loop
---

# Babysit SD PR

Fully autonomous PR maintenance with a **built-in recurring loop**. Checks all three health dimensions (merge conflicts, review feedback, build failures), fixes everything it can in a single pass, commits, pushes, and resolves comments — no user prompts. Self-schedules via `CronCreate` so no separate `/loop` invocation is needed.

## Parameters

```
/babysit-pr [PR_NUMBER] [INTERVAL]
```

- **PR_NUMBER** (optional): The PR number to babysit
  - If not provided, auto-detect from the current branch using `gh pr view`
- **INTERVAL** (optional): How often to re-check, in minutes (default: `5`)
  - Examples: `5` = every 5 minutes, `10` = every 10 minutes, `15` = every 15 minutes

## When to Invoke

- User says "babysit my PR", "keep my PR healthy", "watch my PR"
- When user wants hands-free PR maintenance — no need for a separate `/loop`
- Single invocation: `/babysit-pr` — sets up the loop and runs the first check immediately

---

## CRITICAL: Autonomous Mode

This skill operates **without user confirmation**. It must:

- Fix and push immediately — do not ask "would you like me to..."
- Resolve review threads after addressing them — do not ask first
- Commit and push after each fix category — do not wait for approval
- Log what it did clearly so the user can review after the fact

If something cannot be fixed autonomously (e.g., reviewer is asking a design question that requires human judgment), skip it and note it in the summary.

---

## Step 0: Self-Schedule Recurring Loop

On the **first invocation only**, use `CronCreate` to schedule this skill to re-run automatically.

### 0a. Check if already scheduled

Use `CronList` to check if a babysit-pr job already exists. If one is already running, skip scheduling and proceed directly to Step 1 (this is a recurring invocation).

### 0b. Schedule the loop

If no existing job is found, create one:

```
CronCreate:
  cron: "*/${INTERVAL:-5} * * * *"    # e.g., "*/5 * * * *" for every 5 minutes
  prompt: "/babysit-pr ${PR_NUMBER}"
  recurring: true
```

Pick an off-minute if the interval allows (e.g., `3,8,13,...` instead of `0,5,10,...`) to avoid congestion.

### 0c. Confirm to user

On the first invocation, inform the user:

```
Babysitter activated for PR #1234. Running every 5 minutes.
First check starting now...

To stop: /babysit-pr stop  (or use CronDelete with the job ID)
Note: Auto-expires after 3 days per session limits.
```

### 0d. Auto-cancel when PR is merged/closed

If during any check the PR state is MERGED or CLOSED:

1. Use `CronDelete` to remove the recurring job
2. Report: "PR #{number} is {state}. Babysitter stopped."

### 0e. Handle "stop" argument

If the user runs `/babysit-pr stop`:

1. Use `CronList` to find the babysit job
2. Use `CronDelete` to remove it
3. Report: "Babysitter stopped for PR #1234."
4. Do not proceed to Step 1.

---

## Step 1: Detect PR and Sync Branch

```bash
# Auto-detect or use provided PR number
gh pr view ${PR_NUMBER:---json number,title,url,headRefName,baseRefName,state,mergeable,mergeStateStatus}
```

Extract:

- PR number, title, branch info
- `mergeable` status (MERGEABLE, CONFLICTING, UNKNOWN)
- `mergeStateStatus` (CLEAN, DIRTY, HAS_HOOKS, UNSTABLE, BEHIND, BLOCKED)

If PR is MERGED or CLOSED:

1. Use `CronList` + `CronDelete` to cancel the recurring babysit job
2. Report: "PR #{number} is {state}. Babysitter stopped."
3. Stop here.

Ensure we're on the correct branch and up to date:

```bash
PR_BRANCH=$(gh pr view "${PR_NUMBER}" --json headRefName --jq '.headRefName')
git fetch origin
git checkout "${PR_BRANCH}"
git pull origin "${PR_BRANCH}"
```

---

## Step 2: Check and Fix Merge Conflicts

### 2a. Detect conflicts

Check `mergeable` from Step 1. If `CONFLICTING`:

```bash
# Attempt to merge the base branch to surface conflicts
git fetch origin main
git merge origin/main --no-edit
```

### 2b. Resolve conflicts

If merge produces conflicts:

1. Run `git diff --name-only --diff-filter=U` to list conflicted files
2. For each conflicted file:
   - Read the file to understand the conflict markers
   - Analyze both sides of the conflict
   - Resolve by keeping the intent of both changes where possible
   - If the PR's changes conflict with main, prefer the PR's changes but incorporate any new additions from main
   - Use the Edit tool to remove conflict markers and apply the resolution
3. Stage resolved files: `git add <resolved_files>`
4. Complete the merge: `git commit --no-edit`
5. Push: `git push origin "${PR_BRANCH}"`

### 2c. If conflicts cannot be auto-resolved

If a conflict is too complex (e.g., both sides changed the same logic in incompatible ways):

- Abort the merge: `git merge --abort`
- Note it in the summary as requiring manual resolution
- Continue to the next steps (feedback and builds)

---

## Step 3: Address Review Feedback

### 3a. Fetch unresolved threads

```bash
OWNER_REPO=$(gh repo view --json owner,name --jq '.owner.login + "/" + .name')
OWNER=$(echo "$OWNER_REPO" | cut -d/ -f1)
REPO=$(echo "$OWNER_REPO" | cut -d/ -f2)

gh api graphql -f query='query($owner: String!, $repo: String!, $pr: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        totalCount
        edges {
          node {
            id
            isResolved
            isOutdated
            path
            line
            startLine
            comments(first: 10) {
              edges {
                node {
                  id
                  body
                  author { login }
                  createdAt
                }
              }
            }
          }
        }
      }
    }
  }
}' -f owner="${OWNER}" -f repo="${REPO}" -F pr=${PR_NUMBER}
```

Filter to **unresolved, non-outdated** threads.

If zero unresolved threads, skip to Step 4.

### 3b. Categorize each thread

For each unresolved thread, categorize:

- **Actionable** (code change needed): bug fix, style, performance, safety, refactor, nit
- **Question** (reply needed, no code change): reviewer asking "why did you..."
- **Design discussion** (skip — needs human): architectural disagreement, scope question

### 3c. Address actionable threads

For each actionable thread:

1. Read the file at the referenced path (with context around the commented line)
2. Read the full comment thread to understand the latest ask
3. Apply the fix using the Edit tool
4. Track what was changed for the commit message

### 3d. Reply to question threads

For questions where the answer is clear from the code:

```bash
gh api graphql -f query='mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: $threadId
    body: $body
  }) {
    comment { id }
  }
}' -f threadId='{THREAD_ID}' -f body='{REPLY}'
```

### 3e. Resolve addressed threads (MANDATORY)

**Every thread that has been addressed — whether by a code fix or a reply — MUST be resolved.** Do not leave addressed threads open. This is critical for signaling progress to reviewers.

For each addressed thread, call the `resolveReviewThread` mutation:

```bash
gh api graphql -f query='mutation($threadId: ID!) {
  resolveReviewThread(input: {threadId: $threadId}) {
    thread { id isResolved }
  }
}' -f threadId='{THREAD_ID}'
```

Only skip resolving a thread if it was categorized as "design discussion" and left for human input.

### 3f. Commit and push feedback changes

If any code changes were made:

```bash
git add <changed_files>
git commit -m "fix: address PR review feedback

- [summary of each change per thread]

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin "${PR_BRANCH}"
```

---

## Step 4: Check and Fix Build Failures

### 4a. Fetch PR checks

```bash
gh pr checks "${PR_NUMBER}"
```

Parse for failing Screwdriver checks. If all checks pass or are pending, skip to Step 5.

### 4b. Identify and prioritize failures

Priority order:

1. `build-pr` (compilation) — blocks everything
2. `test` — test failures
3. `lint` — style violations
4. Other jobs

Extract the build ID from the failing check URL.

### 4c. Fetch and analyze build logs

```bash
./scripts/screwdriver/sd-investigate-build.sh "${BUILD_ID}"
```

Fallback if script fails:

```bash
sd4 build logs -b "${BUILD_ID}" 2>&1 | tail -200
```

### 4d. Diagnose and fix

Analyze logs to identify root cause. Common patterns:

- **Compilation error**: Fix missing imports, type errors, syntax issues
- **Test failure**: Fix broken assertions, missing mocks, NPEs
- **Lint/style**: Run formatter, fix style violations
- **Corrupted cache**: Run `./scripts/screwdriver/sd-clear-cache.sh be-replay` and re-trigger build — no code fix needed

For code fixes:

1. Apply the fix using Edit tool
2. Verify locally:
   ```bash
   # For compilation
   ./gradlew compileJava compileTestJava
   # For test failures
   ./gradlew test --tests "*FailingTestClass*"
   # For style
   ./gradlew spotlessApply
   ```
3. Commit and push:

   ```bash
   git add <changed_files>
   git commit -m "fix: resolve ${FAILURE_TYPE} in ${COMPONENT}

   Build: ${BUILD_ID}
   PR: #${PR_NUMBER}

   Co-Authored-By: Claude <noreply@anthropic.com>"

   git push origin "${PR_BRANCH}"
   ```

### 4e. If build failure cannot be auto-fixed

If the root cause is unclear or requires architectural changes:

- Note it in the summary
- Suggest `/troubleshoot-pipeline ${PR_NUMBER} ${BUILD_ID}` for deeper investigation

---

## Step 5: Summary Report

After completing all steps, present a concise summary:

```markdown
## PR Babysitter Report

**PR:** #1234 — feat: add agent tracking
**Branch:** feature/agent-tracking -> main
**Time:** 2026-03-24 14:30 UTC

### Merge Conflicts

- Status: No conflicts / Resolved 3 conflicts / 1 conflict needs manual resolution

### Review Feedback

- Threads addressed: 4 of 5
- Threads resolved: 4
- Threads skipped: 1 (design question — needs human input)
  - @reviewer on FooService.java:42: "Should we use a different pattern here?"
- Commit: `abc1234` fix: address PR review feedback

### Build Status

- Previous: FAIL (build #127658225 — test failure)
- Fix applied: resolved NPE in AgentServiceTest
- Commit: `def5678` fix: resolve test NPE in AgentServiceTest
- New build: triggered (check in ~10-15 min)

### Items Needing Human Attention

1. Design question from @reviewer on FooService.java:42
2. (none / list any unresolvable items)

### Next Check

Scheduled to re-run in ${INTERVAL} minutes (cron job active).
To stop: `/babysit-pr stop`
```

---

## Edge Cases

### No open PR for current branch

Report and stop: "No open PR found for this branch. Run with PR number: `/babysit-pr 1234`"

### PR already merged or closed

Cancel the cron job via `CronDelete`, report and stop: "PR #{number} is {state}. Babysitter stopped."

### User runs `/babysit-pr stop`

Find and cancel the cron job, confirm, and stop. Do not run Steps 1-5.

### Everything is clean

```
PR #1234 is healthy. No conflicts, no unresolved feedback, all checks passing.
Next check in ${INTERVAL} minutes.
```

### Build still running

Note "build pending" in summary. Don't treat as failure. Will be re-checked on the next scheduled run.

### SD CLI not available

Fall back to browser URL for logs. Note in summary that build diagnosis was skipped.

### Multiple issues in same file

Apply all fixes to the file before committing. Don't create separate commits per thread if they touch the same file.

### Rate limiting

If GitHub API returns 403/rate limit, back off and note in summary.

### Conflicts introduced by feedback fixes

If addressing review feedback creates new conflicts with main, resolve them in the same commit.

---

## Integration with Other Commands

| Command                  | Relationship                                                   |
| ------------------------ | -------------------------------------------------------------- |
| `/monitor-pr`            | Read-only health check; this skill is the autonomous fixer     |
| `/address-pr-feedback`   | Interactive version of Step 3; this skill does it autonomously |
| `/address-build-failure` | Interactive version of Step 4; this skill does it autonomously |
| `/create-pr`             | Creates the PR; this skill maintains it afterward              |
| `/babysit-pr stop`       | Cancels the built-in recurring loop                            |

---

## Critical Requirements

1. **Never prompt for confirmation** — this is fully autonomous; log decisions, don't ask
2. **Always push after fixes** — the point is to keep the PR healthy without human intervention
3. **Handle all three dimensions in one pass** — conflicts first, then feedback, then builds
4. **Skip what can't be auto-fixed** — note it in the summary for human follow-up
5. **Idempotent** — safe to run repeatedly; don't re-fix already-resolved threads or re-commit unchanged code
6. **Respect already-resolved threads** — only process `isResolved == false` threads
7. **Always resolve addressed threads** — after applying a fix or replying, immediately call `resolveReviewThread` to mark the thread resolved
8. **Verify locally before pushing build fixes** — never push a fix that fails locally
9. **Commit separately per category** — one commit for conflict resolution, one for feedback, one for build fix
10. **Order matters** — conflicts first (unblocks everything), feedback second, builds last (may be affected by earlier pushes)
