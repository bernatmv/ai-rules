# Live UI library sources

Use these links to inspect the current catalog when designing a UI. They are entry points, not a fixed inventory. Check for an official MCP in the available tools and the provider's current documentation before browsing; if one exists, use it to discover candidates and read their details. Do not add a dependency on an undocumented MCP.

| Source | Live discovery path | Integration check |
| --- | --- | --- |
| [Interior](https://www.interior.dev/docs) | Browse the docs categories and individual component pages; the [source repository](https://github.com/ddoemonn/interior) and per-component shadcn registry entries expose code. | React, Tailwind, and Motion; source is copied into the app. Compare its headless behavior and styled example with the app's existing primitives. |
| [Beautiful UI](https://www.beautifului.dev/) | Browse the gallery and its [component registry](https://www.beautifului.dev/r/registry.json), or inspect the [source repository](https://github.com/slev12397/beautiful-ui). | AI product focus. Check each component's dependency tree and shared Tailwind v4 foundation before integrating; the repository notes a paid icon dependency in its demo sidebar. |
| [Cuelume](https://cuelume.dev/docs) | Browse the [sound catalog](https://cuelume.dev/) and current docs; use its [agent guide](https://cuelume.dev/agents.md) when accessible. | Web Audio, ESM, browser playback. Keep sound optional and user-controlled; connect cues to real application events and verify the silent experience. |

No MCP endpoint is hard-coded here. Recheck the provider's current docs and the tools available in the task; new MCP servers, registry entries, and components may appear. A third-party catalog is useful for discovery, but confirm installation and API details against the library's own docs or source.
