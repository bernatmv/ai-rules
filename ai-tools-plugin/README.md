# ai-tools-plugin

HeyGen AI video and avatar skills for Claude Code.

## Dependencies

Installing `ai-tools-plugin@ai-rules` auto-installs:

| Plugin | Marketplace | Provides |
| --- | --- | --- |
| `heygen` | `heygen` | Avatar videos, TTS, translation, video generation, and editing ([heygen-com/skills](https://github.com/heygen-com/skills)) |

The [heygen-com/skills catalog](https://claudemarketplaces.com/skills/heygen-com/skills) lists 11 skill entry points (`heygen`, `text-to-speech`, `video-translate`, `video-understand`, `video-edit`, `avatar-video`, `ai-video-gen`, `create-video`, `video-download`, `visual-style`, `faceswap`). The Claude plugin bundles them via `heygen@heygen`:

| Skill | Slash command |
| --- | --- |
| Avatar / digital identity | `/heygen:avatar` |
| Presenter video generation | `/heygen:video` |
| Video translation / dubbing | `/heygen:translate` |

Requires a [HeyGen API key](https://app.heygen.com/api) for most workflows. See upstream [INSTALL.md](https://github.com/heygen-com/skills/blob/master/INSTALL.md).

Complements `frontend-plugin` video tooling (`hyperframes`, `remotion-plugin`) — HeyGen handles avatar/TTS/translation APIs; HyperFrames/Remotion handle programmatic HTML/React video.

See [`.claude/SKILLS.md`](../.claude/SKILLS.md) for skill → plugin mapping.

## Install

```sh
/plugin marketplace add heygen-com/skills
/plugin marketplace add bernatmv/ai-rules
/plugin install ai-tools-plugin@ai-rules
/reload-plugins
```
