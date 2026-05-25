#!/usr/bin/env bash
set -euo pipefail

# create-skill.sh
#
# Creates a new skill in the skills/ directory with:
#   skills/<skill-name>/SKILL.md
#   skills/<skill-name>/{assets,examples,scripts}/
#
# Usage:
#   ./create-skill.sh <skill-name> [more-skill-names...]
#   ./create-skill.sh my-skill
#   ./create-skill.sh skill-one skill-two skill-three
#
# Notes:
# - Must be run from plugin root directory (where skills/ exists)
# - Skill folder names should be kebab-case (recommended)
# - SKILL.md frontmatter includes required fields: name, description

show_help() {
  cat <<EOF
Usage: create-skill.sh [OPTIONS] SKILL_NAME [SKILL_NAME...]

Create one or more new skills in the skills/ directory with templated
structure and SKILL.md file.

ARGUMENTS:
  SKILL_NAME              Name(s) of skill(s) to create (kebab-case recommended)
                         Multiple skill names can be provided to create several at once

OPTIONS:
  -d, --plugin-dir DIR    Plugin directory path (default: current directory)
  -y, --yes               Skip confirmation prompt and proceed automatically
  --help, -h              Show this help message and exit

DESCRIPTION:
  Creates the following structure for each skill:
    skills/<skill-name>/SKILL.md          Main skill definition with YAML frontmatter
    skills/<skill-name>/assets/           Images, diagrams, and other assets
    skills/<skill-name>/examples/         Usage examples
    skills/<skill-name>/scripts/          Helper scripts

  The generated SKILL.md includes:
    - YAML frontmatter with name and description fields
    - Sections for Purpose, Inputs, Steps, Outputs, and Examples
    - Placeholder content to guide skill development

EXAMPLES:
  # Create a single skill
  ./create-skill.sh my-awesome-skill

  # Create multiple skills at once
  ./create-skill.sh skill-one skill-two skill-three

  # Skill names with spaces are converted to kebab-case
  ./create-skill.sh "My New Skill"  # Creates: my-new-skill

  # Create skills without confirmation prompt
  ./create-skill.sh my-skill -y

  # Specify a plugin directory
  ./create-skill.sh --plugin-dir /path/to/plugin my-skill

  # Combine options
  ./create-skill.sh -d /path/to/plugin -y my-skill

NOTES:
  - By default, uses current directory as plugin root
  - Use --plugin-dir to specify a different plugin directory
  - Run init-plugin.sh first if skills/ directory doesn't exist
  - Existing SKILL.md files will NOT be overwritten
  - Skill names are sanitized: spaces → dashes, special chars removed
  - Only alphanumeric characters, dashes, and underscores are allowed

SKILL.MD FORMAT:
  Each skill requires YAML frontmatter with:
    name:        Skill identifier (required)
    description: What the skill does and when to use it (required)
    license:     Optional license identifier
    metadata:    Optional author, version, etc.
EOF
}

SKIP_CONFIRM="0"
PLUGIN_DIR="."
SKILL_NAMES=()

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h)
      show_help
      exit 0
      ;;
    -y|--yes)
      SKIP_CONFIRM="1"
      shift
      ;;
    -d|--plugin-dir)
      if [[ -z "${2:-}" ]]; then
        echo "Error: --plugin-dir requires a directory path" >&2
        exit 1
      fi
      PLUGIN_DIR="$2"
      shift 2
      ;;
    -*)
      echo "Error: Unknown option: $1" >&2
      echo "Run '$0 --help' for usage information." >&2
      exit 1
      ;;
    *)
      SKILL_NAMES+=("$1")
      shift
      ;;
  esac
done

if [[ "${#SKILL_NAMES[@]}" -lt 1 ]]; then
  echo "Usage: $0 [OPTIONS] SKILL_NAME [SKILL_NAME...]" >&2
  echo "Run '$0 --help' for more information." >&2
  exit 1
fi

# Check that plugin directory exists
if [[ ! -d "$PLUGIN_DIR" ]]; then
  echo "Error: Plugin directory not found: $PLUGIN_DIR" >&2
  exit 1
fi

# Check that skills/ directory exists
if [[ ! -d "$PLUGIN_DIR/skills" ]]; then
  echo "Error: skills/ directory not found in: $PLUGIN_DIR" >&2
  echo "Hint: Run 'init-plugin.sh' first to initialize the plugin structure." >&2
  exit 1
fi

sanitize_name() {
  # keep it simple: allow letters/numbers/dash/underscore; replace spaces with dash
  echo "$1" | tr ' ' '-' | tr -cd '[:alnum:]_-'
}

# Prompt for confirmation unless -y flag is provided
if [[ "$SKIP_CONFIRM" == "0" ]]; then
  # Resolve absolute path for display
  PLUGIN_DIR_ABS="$(cd "$PLUGIN_DIR" && pwd)"
  echo "This will create the following skill(s) in: $PLUGIN_DIR_ABS/skills/"
  for raw in "${SKILL_NAMES[@]}"; do
    sanitized="$(sanitize_name "$raw")"
    if [[ -n "$sanitized" ]]; then
      echo "  - $sanitized/"
      echo "    - SKILL.md"
      echo "    - assets/ examples/ scripts/"
    fi
  done
  echo
  read -p "Continue? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

for raw in "${SKILL_NAMES[@]}"; do
  SKILL_DIR_NAME="$(sanitize_name "$raw")"
  if [[ -z "$SKILL_DIR_NAME" ]]; then
    echo "Skipping empty/invalid skill name: '$raw'" >&2
    continue
  fi

  SKILL_PATH="$PLUGIN_DIR/skills/${SKILL_DIR_NAME}"
  mkdir -p "${SKILL_PATH}/"{assets,examples,scripts}

  if [[ ! -f "${SKILL_PATH}/SKILL.md" ]]; then
    cat > "${SKILL_PATH}/SKILL.md" <<EOF
---
name: ${SKILL_DIR_NAME}
description: TODO - Describe what this skill does and when an agent should use it.
# Optional fields you may add:
# license: Apache-2.0
# metadata:
#   author: your-name-or-org
#   version: "0.1.0"
---

# ${SKILL_DIR_NAME}

## Purpose
- What problem this skill solves
- When to use it / when not to use it

## Inputs
- What the agent needs (files, prompts, environment, access)

## Steps
1. Step-by-step workflow the agent should follow
2. Include checks, failure modes, and "done" criteria

## Outputs
- What artifacts or results should be produced

## Examples
See \`examples/\`.
EOF
    echo "Created: ${SKILL_PATH}/SKILL.md"
  else
    echo "Exists, not overwriting: ${SKILL_PATH}/SKILL.md"
  fi
done

# Resolve absolute path for final message
PLUGIN_DIR_ABS="$(cd "$PLUGIN_DIR" && pwd)"
echo "Skill(s) created under: $PLUGIN_DIR_ABS/skills/"
