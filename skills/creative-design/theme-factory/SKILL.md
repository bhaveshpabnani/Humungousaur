---
name: theme-factory
description: Create or apply visual themes with accessible color, typography, spacing, component states, and consistency across an existing interface.
---

# Theme Factory

## Purpose

Design coherent themes that fit a product and remain usable. The assistant should avoid one-note palettes and decorative excess.

## When To Use

Use for color/theme systems, dark/light modes, design tokens, typography, component styling, and visual refreshes.

## Inputs And Evidence

- Existing CSS/tokens, brand constraints, screenshots, accessibility needs, and target mood.
- Browser verification artifacts.

## Tool Map

- `read_file`
- `search_workspace`
- `theme_pack_create`
- `theme_pack_inspect`
- `frontend-design`
- `browser_live_observe`
- `browser_live_screenshot`
- `web-data-extraction`

## Workflow

1. Inspect current token/style structure.
2. Use `theme_pack_create` to define palette, typography, spacing, radius, component states, contrast checks, and generated CSS variables.
3. Avoid dominant single-hue themes unless brand requires it.
4. Use `theme_pack_inspect` before applying the theme in existing styling architecture.
5. Verify contrast, text fit, and layout.
6. Document the theme rules when useful.

## Native Implementation Boundaries

- Use project-owned CSS/code.
- Do not import Anthropic theme-factory code.
- Do not add styling libraries without approval.
- Theme-pack artifacts are local specs and CSS sidecars; they are not applied to app code until separate edits are made.

## Safety And Approval

- Preserve brand/legal requirements.
- Avoid low contrast or motion-heavy themes.
- Keep accessibility in scope.

## Verification

- Browser screenshots prove theme application.
- Check major states and viewports.
- Inspect theme-pack artifacts and CSS sidecars before applying.
- Report contrast or responsive gaps.

## Failure Modes

- Pretty palette with unreadable text.
- Inconsistent component states.
- Theme changes leaking into unrelated surfaces.

## References

- Shortlist item: `theme-factory`.
