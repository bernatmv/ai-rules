#!/usr/bin/env bash
set -euo pipefail

file=$(jq -r '.tool_input.file_path // .tool_input.path // ""')
[[ -n "$file" && -f "$file" ]] || exit 0

case "$file" in
  *.js|*.jsx|*.ts|*.tsx|*.json|*.css|*.scss|*.html|*.md|*.yaml|*.yml)
    npx prettier --write "$file" 2>/dev/null || true
    ;;
esac

case "$file" in
  *.js|*.jsx|*.ts|*.tsx)
    npx eslint --fix "$file" 2>&1 | tail -10 || true
    ;;
esac

exit 0
