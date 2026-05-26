---
name: plugin-advisor
tags: []
description: >
  Suggests uninstalled marketplace plugins on friction. Triggered passively.
  Use when agent retries, user corrects approach, or no good tool exists.
  Out of scope: plugin installation, plugin development, MCP server setup.
allowed-tools: Bash(ls *) Bash Read Write Agent
---

**plugin-advisor skill loaded.**

By Joshua Martell (jmartell). Originally from claude-kit.

## How It Works

A compact plugin index lives at `~/.claude_files/plugin-index.md`. Each line is
one plugin with its source and a short description. The index is built by a
Sonnet subagent reading `marketplace.json` — no Python script needed.

**On load**, check freshness and rebuild if the index is missing or stale (see
Freshness Check). This ensures the index is warm before friction occurs.

## Freshness Check

Use `ls -l` (not `stat` — stat triggers quoted-chars permission prompts):

```
ls -l ~/.claude/plugins/marketplaces/*/.claude-plugin/marketplace.json
```

Then read the index (`~/.claude_files/plugin-index.md`) and compare each marketplace
section's `<!-- source:` metadata against the `ls -l` output. Rebuild if:

- Index doesn't exist
- A marketplace file's size or mtime differs from what's in the section header
- A marketplace appears in `ls -l` but has no section in the index (new marketplace)

## Friction Detection

Consider suggesting a plugin when you observe **two or more** of these signals:

- You attempted something and it failed or produced poor results
- The user corrected your approach or expressed dissatisfaction
- You're retrying the same task with a different strategy
- You don't have a good tool/workflow for what's being asked
- The task is in a domain where you're improvising (hooks, PR review, interactive UI)

**Do not suggest** on first attempt. Only after genuine friction.

## When Friction Is Detected

1. Check freshness (see above). Rebuild if stale.
2. Read `~/.claude_files/plugin-index.md`
3. Scan for a plugin whose description matches the problem domain
4. If a match looks strong, read the full plugin directory to confirm:
   `~/.claude/plugins/marketplaces/*/plugins/<name>/` (Anthropic first-party)
   `~/.claude/plugins/marketplaces/*/external_plugins/<name>/` (vendor/external)
5. For vendor/external plugins, check what's involved (MCP gateway? service account?)
6. If confirmed, suggest it

## Suggestion Format

Brief, one line, with install command:

> **Plugin available:** `playground` — self-contained HTML explorers with live preview.
> Install: `claude plugin install playground`

Then continue working on the task. The suggestion is informational — don't stop.

## Rules

- **Max 1 suggestion per plugin per session** — don't nag
- **Max 1 suggestion per ~10 turns** — spread them out
- **Never suggest already-installed plugins** — check `~/.claude/plugins/installed_plugins.json`
- **Check for skill overlap** — the user's installed skills (visible in the skills
  list in context) may already cover the plugin's capability. If there's overlap,
  note it: "You already have the `jira` skill which covers this" rather than suggesting
- **Layer 2 confirmation required** — always read the full plugin dir before
  suggesting to verify the plugin actually addresses the friction
- **No sales pitch** — state what it does, give the install command, move on

## Rebuilding the Index

When the index is stale or missing, launch a Sonnet subagent with this prompt.
Pass the `ls -l` output as context so the subagent can embed the metadata.

```
Build a compact plugin index. Use ONLY Read and Write tools. No Bash.

For EACH marketplace directory under ~/.claude/plugins/marketplaces/:
  Read: ~/.claude/plugins/marketplaces/<name>/.claude-plugin/marketplace.json

Skip rules:
- Skip plugins with "-lsp" in the name
- Skip "example-plugin"

For each kept plugin, write one line:
  name (source): description (under 70 chars, specific to when it helps)

Source labels:
- "Anthropic" if source starts with "./plugins/"
- "vendor" if source starts with "./external_plugins/"
- Author/org name if source is a URL

Drop any plugin whose description is too vague to match a specific problem.

Output format — one section per marketplace, with source metadata from the
ls -l output I'm providing:

  # Available Plugins
  # On friction, suggest matching plugin: claude plugin install <name>

  ## claude-plugins-official
  <!-- source: 548512 Mar 13 14:23 marketplace.json -->
  plugin-name (Anthropic): description
  another-plugin (vendor): description

  ## devex-claude-plugins
  <!-- source: 12345 Mar 12 09:15 marketplace.json -->
  some-plugin (vendor): description

The <!-- source: SIZE DATE TIME marketplace.json --> line stores the size and
mtime from ls -l. Use the actual values from the ls -l output below:

{paste ls -l output here}
```
