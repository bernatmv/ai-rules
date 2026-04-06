# Location

`~/.cursor/skills/`

# Skills list

## Claude Code skills parity

Skills already in Claude Code will be discovered by cursor, those added as plugins to Claude need to be copied over (folders inside `/skills`).

## Claude MEM

_DO NOT INSTALL_ (Claude plugin)

if really needed:

```sh
# Bun (if needed)
curl -fsSL https://bun.sh/install | bash
# jq and curl
brew install jq curl
# Clone and build
git clone https://github.com/thedotmack/claude-mem.git
cd claude-mem && bun install && bun run build

# Interactive setup (configures provider + installs hooks)
bun run cursor:setup

# Install globally for all projects (recommended)
claude-mem cursor install user

# Or install for current project only
claude-mem cursor install

# Start the worker
claude-mem start
```
