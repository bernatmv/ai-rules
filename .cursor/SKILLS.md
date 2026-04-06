# Location

`~/.cursor/skills/`

# Skills list

## Frontend design

`npx skills add anthropics/claude-code - skill frontend-design`

## PDF

`npx skills add anthropics/claude-code - skill pdf`

## Skill creator

`npx skills add anthropics/claude-code - skill skill-creator`

## Web artifacts builder

`npx skills add anthropics/claude-code - skill web-artifacts-builder`

## Web asset generator

`npx skills add anthropics/claude-code - skill web-asset-generator`

## Webapp testing

`npx skills add anthropics/claude-code - skill webapp-testing`

## Browser use

`npx skills add https://github.com/browser-use/browser-use --skill browser-use`

## Code Reviewer

`npx claude-code-templates@latest --skill development/code-reviewer`

## Remotion

`npx skills add remotion/agent-skills`

Then in Claude:

```sh
/remotion Create a 30-second product demo video showing our API
dashboard with animated charts and transitions
```

## Excalidraw

`npx skills add https://github.com/coleam00/excalidraw-diagram-skill --skill excalidraw-diagram`

## Shadcn

`npx skills add shadcn/ui`

## Vercel skills

`npx skills add vercel-labs/agent-skills`

## Next best practices

`npx skills add https://github.com/vercel-labs/next-skills --skill next-best-practices`

## Create screenshots for app

`npx skills add ParthJadhav/app-store-screenshots`

Build App Store screenshots
Generate marketing screenshots for an iOS app
Create exportable screenshot assets

## Visual explainer

Copy skill folder (it's a Claude plugin)

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
