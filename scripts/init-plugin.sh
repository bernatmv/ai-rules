#!/usr/bin/env bash
set -euo pipefail

# init-plugin.sh
#
# Creates a plugin repository structure:
#   .claude-plugin/plugin.json
#   docs/
#   tests/
#   commands/
#   skills/
#   README.md
#   commands/README.md
#   tests/validate-skills.sh
# plus optional .github/skills symlink for GitHub Copilot.
#
# Usage:
#   ./init-plugin.sh [plugin-dir] [--symlink-copilot]
#   ./init-plugin.sh .
#   ./init-plugin.sh my-plugin --symlink-copilot
#

show_help() {
  cat <<EOF
Usage: init-plugin.sh [OPTIONS] [PLUGIN_DIR]

Initialize a new Agent plugin repository structure with standard directories
and template files.

ARGUMENTS:
  PLUGIN_DIR              Directory to initialize as a plugin (default: current directory)

OPTIONS:
  --symlink-copilot       Create .github/skills symlink for GitHub Copilot integration
  -y, --yes               Skip confirmation prompt and proceed automatically
  --help, -h              Show this help message and exit

DESCRIPTION:
  Creates the following directory structure:
    .claude-plugin/plugin.json  Plugin metadata (name, version, description)
    skills/               Agent skills (each with SKILL.md)
    docs/                 Documentation files
    tests/                Validation and test scripts
    commands/             CLI commands and executables
    README.md             Root repository documentation
    commands/README.md    Commands directory documentation
    tests/validate-skills.sh  Skill validation script

EXAMPLES:
  # Initialize current directory as a plugin
  ./init-plugin.sh

  # Initialize a new plugin directory
  ./init-plugin.sh my-plugin

  # Initialize with GitHub Copilot symlink
  ./init-plugin.sh my-plugin --symlink-copilot

  # Initialize current directory with Copilot support
  ./init-plugin.sh . --symlink-copilot

  # Initialize without confirmation prompt
  ./init-plugin.sh my-plugin -y

NOTES:
  - Existing files will not be overwritten
  - The --symlink-copilot flag creates: .github/skills -> ../skills
  - Skill validation script template is created but needs configuration
EOF
}

SYMLINK_COPILOT="0"
PLUGIN_DIR="."
SKIP_CONFIRM="0"

args=()
for a in "$@"; do
  case "$a" in
    --help|-h)
      show_help
      exit 0
      ;;
    --symlink-copilot) SYMLINK_COPILOT="1" ;;
    -y|--yes) SKIP_CONFIRM="1" ;;
    *) args+=("$a") ;;
  esac
done

if [[ "${#args[@]}" -ge 1 ]]; then
  PLUGIN_DIR="${args[0]}"
fi

mkdir -p "$PLUGIN_DIR"
cd "$PLUGIN_DIR"

# Prompt for confirmation unless -y flag is provided
if [[ "$SKIP_CONFIRM" == "0" ]]; then
  echo "This will create the following structure in: $(pwd)"
  echo "  - .claude-plugin/plugin.json"
  echo "  - skills/ docs/ tests/ commands/ (directories)"
  echo "  - README.md"
  echo "  - commands/README.md"
  echo "  - tests/validate-skills.sh"
  if [[ "$SYMLINK_COPILOT" == "1" ]]; then
    echo "  - .github/skills -> ../skills (symlink)"
  fi
  echo
  read -p "Continue? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

# Create directory structure
mkdir -p skills docs tests commands hooks agents mcp-servers .claude-plugin

# Plugin metadata (only if it doesn't exist)
if [[ ! -f .claude-plugin/plugin.json ]]; then
  # Get directory name as default plugin name
  PLUGIN_NAME="$(basename "$(pwd)")"
  cat > .claude-plugin/plugin.json <<EOF
{
  "name": "${PLUGIN_NAME}",
  "version": "1.0.0",
  "description": "TODO: Add a description of what this plugin does",
  "author": {
    "name": "TODO: Add author name"
  }
}
EOF
fi

# Root README (only if it doesn't exist)
if [[ ! -f README.md ]]; then
  cat > README.md <<'EOF'
# Agent Plugin

This plugin contains Agent Skills and commands in the open `SKILL.md` format.

## Structure
- `skills/<skill-name>/SKILL.md` (required entrypoint for each skill)
- `skills/<skill-name>/scripts/` (optional helper scripts)
- `skills/<skill-name>/examples/` (optional examples)
- `skills/<skill-name>/assets/` (optional images/diagrams)
- `commands/` (CLI commands or executables)
- `docs/` (documentation)
- `tests/` (validation and tests)

## Add a new skill
Use the `create-skill.sh` script or manually create a folder under `skills/` with a `SKILL.md` file containing YAML frontmatter:
- `name` (required)
- `description` (required)
EOF
fi

# Commands README stub (only if it doesn't exist)
if [[ ! -f commands/README.md ]]; then
  cat > commands/README.md <<'EOF'
# Commands

This directory contains CLI commands, executables, or scripts that can be invoked by users or agents.

## Structure
Place your command scripts or binaries here. Ensure they are executable:
```bash
chmod +x commands/your-command.sh
```

## Usage
Commands can be invoked directly or referenced by skills in the `skills/` directory.
EOF
fi

# Optional validation helper script (non-fatal if tools aren't installed)
if [[ ! -f tests/validate-skills.sh ]]; then
  cat > tests/validate-skills.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "Validating skills folders..."
# If you have skills-ref installed:
#   skills-ref validate ./skills
# Or if you use the `skills` CLI:
#   npx skills validate ./skills
echo "Done (configure a validator in this script as desired)."
EOF
  chmod +x tests/validate-skills.sh
fi

if [[ "$SYMLINK_COPILOT" == "1" ]]; then
  mkdir -p .github
  # Create or replace .github/skills symlink to ./skills
  if [[ -e ".github/skills" || -L ".github/skills" ]]; then
    rm -rf ".github/skills"
  fi
  ln -s "../skills" ".github/skills"
  echo "Created symlink: .github/skills -> ../skills"
fi

echo "Plugin initialized at: $(pwd)"
echo "Created: .claude-plugin/plugin.json (update name, version, description, and author)"
echo "Directory structure created: skills/, docs/, tests/, commands/"
