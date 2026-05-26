# Design Drift Criteria

Conditional dimension — load only when changed files include frontend/UI code
(`.tsx`, `.jsx`, `.vue`, `.svelte`, `.html`, `.css`, `.scss`, or files in
directories named `components`, `pages`, `views`, `screens`, `layouts`).

## Contents
- [Applicability Check](#applicability-check)
- [Design Drift Checks](#design-drift-checks)

---

## Applicability Check

Skip this dimension entirely if:
- No frontend files in the changed file set
- No `ui-design.md` exists (standalone mode without design reference)

## Design Drift Checks

| # | Check | Pass | Fail |
|---|-------|------|------|
| 1 | **Component structure** | UI components match the component hierarchy in ui-design.md or design.md | Components structured differently than designed |
| 2 | **Layout fidelity** | Layout matches wireframes/mockups described in ui-design.md | Significant layout deviations without documented justification |
| 3 | **Interaction patterns** | User interactions (click, hover, drag) match design specifications | Missing or different interaction behaviors |
| 4 | **Responsive behavior** | Breakpoints and responsive rules match design requirements | Missing responsive handling; hard-coded widths |
| 5 | **State representation** | Loading, error, empty, and success states all implemented per design | Missing states (e.g., no loading indicator, no error state) |
| 6 | **Accessibility** | Semantic HTML; ARIA labels; keyboard navigation; color contrast | Missing alt text; non-semantic markup; no keyboard support |
| 7 | **Design system usage** | Uses project design system tokens/components when available | Custom colors/spacing instead of design tokens; reimplemented components |

> In standalone mode (no spec), evaluate drift against the project's existing
> design patterns and design system rather than spec documents.
