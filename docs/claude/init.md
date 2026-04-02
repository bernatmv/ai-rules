Claude Code docs
https://x.com/akshay_pachaar/status/2035341800739877091

your-project/
├── CLAUDE.md                  # Team instructions (committed)
├── CLAUDE.local.md            # Your personal overrides (gitignored)
│
└── .claude/
    ├── settings.json          # Permissions, hooks, config (committed)
    ├── settings.local.json    # Personal permission overrides (gitignored)
    │
    ├── hooks/                 # Hook scripts referenced by settings.json
    │   ├── bash-firewall.sh   # PreToolUse: block dangerous commands
    │   ├── auto-format.sh     # PostToolUse: format files after edits
    │   └── enforce-tests.sh   # Stop: ensure tests pass before finishing
    │
    ├── rules/                 # Modular instruction files
    │   ├── code-style.md
    │   ├── testing.md
    │   └── api-conventions.md
    │
    ├── skills/                # Auto-invoked workflows
    │   ├── security-review/
    │   │   └── SKILL.md
    │   └── deploy/
    │       └── SKILL.md
    │
    └── agents/                # Specialized subagent personas
        ├── code-reviewer.md
        └── security-auditor.md

~/.claude/
├── CLAUDE.md                  # Your global instructions
├── settings.json              # Your global settings + hooks
├── skills/                    # Your personal skills (all projects)
├── agents/                    # Your personal agents (all projects)
└── projects/                  # Session history + auto-memory