---
name: ui-character-and-polish
description: Add character, depth, and polish when designing or refining a web UI. Audit opportunities for useful new interface moments, then choose fitting micro-interactions, AI UI patterns, and optional sound cues.
---

# UI character and polish

Use this alongside the project's design system and any broader frontend design skill. The goal is a UI that feels responsive, legible, and distinctive. A component library is a source of patterns, not the design direction.

## Work from moments, not widgets

1. Inspect the existing product, visual language, framework, dependencies, and key user journeys. Identify where users act, wait, receive a result, recover, navigate, or notice changed data. For a new UI, map those moments from the proposed flow.
2. Make a short opportunity map: **moment → user need → proposed addition or refinement → expected benefit → cost**. Include new elements when they clarify a journey: task progress, context/source preview, actionable empty state, undo, live activity, or meaningful success feedback. A one-for-one component swap is not the default.
3. Pick a few high-value moments. Give each a deliberate treatment using layout, type, color, depth, motion, copy, or sound. Establish a rhythm across the screen; repeated sparkles, sounds, and motion on every control flatten the hierarchy.
4. Consult the relevant [live library sources](references/libraries.md) for each promising moment. First look for an available official MCP tool or server and use it for discovery if present; otherwise browse the current catalog, registry, and documentation. Consider newly added components as well as established ones. Inspect the chosen component's current source, dependencies, and license before installing or copying it. Adapt tokens, radii, density, icons, and behavior to the product. Preserve existing accessible primitives when a visual effect can be layered onto them.
5. Verify the actual flow in the browser: idle, hover/focus, press, pending, success, error, interrupted interaction, empty state, keyboard, touch, reduced motion, responsive layouts, and sound muted. Check that feedback reflects real application state, never a timer pretending work succeeded.

## Live sources and fit

- [Interior](https://www.interior.dev/docs) for interaction and state details across actions, input, async work, navigation, data, gestures, and content.
- [Beautiful UI](https://www.beautifului.dev/) for AI-native product flows such as agent work, streaming results, approvals, context, and proposed edits.
- [Cuelume](https://cuelume.dev/docs) for optional sound tied to meaningful events or tactile controls. Provide a sound toggle, persist the preference in the app, default conservatively, and keep every state understandable with audio off.

The [source guide](references/libraries.md) gives the current entry points and integration caveats. Treat its links as starting points, not a snapshot of what each library contains. Check the live catalog whenever this skill applies, and do not assume an MCP exists until its provider documents one or it is available in the environment.

These are web libraries. In non-React work, use the interaction idea and implement it in the project's native stack; do not introduce React for polish alone. For a React app, reuse its existing motion, headless, and design-system primitives when they already meet the need.

Use the live sources to propose additions as well as refinements: a clearer async state, a review step for consequential AI actions, a way to inspect retrieved sources, or a small cue when work truly completes. Select only what improves the specific journey, and explain any substantial new UI element in the handoff.
