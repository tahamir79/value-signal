# DamLogics — Frontend Design Guidelines

This file is the design brief for all frontend work on DamLogics. Load it explicitly when doing UI/UX work. Technical constraints (allowed components, colour token rules, accessibility requirements) live in `CLAUDE.md`.

---

## The Aesthetic Direction

DamLogics must feel **authoritative, precise, and purpose-built** — the aesthetic equivalent of a high-end engineering instrument. Every design decision should signal that this is professional infrastructure for critical infrastructure assessment, not a generic SaaS dashboard.

Draw inspiration from: precision instruments, geological survey tools, structural engineering drawings, and cartographic / topographic design. The palette is deep and deliberate — dark navy (`lp-basin`), copper accents (`lp-copper`), off-white chalk (`lp-chalk`) — not default blue/grey. Typography mixes authoritative serif display (Fraunces 900) with crisp data-dense mono (JetBrains Mono).

Aspire to: **rich contrast, dramatic weight differences, generous negative space, and data clarity as the centrepiece.** The aesthetic is bold without being decorative — every element earns its place.

---

## Resist "AI Slop"

Claude tends to converge toward generic, "on distribution" outputs:
- Space Grotesk / Inter headings
- Slate-gray palettes
- Card-grid layouts that could belong to any SaaS product
- Predictable hover states and transitions
- Centred hero with gradient button

**Actively resist this.** Before choosing any visual element, reject the first option that comes to mind and find a less obvious alternative. No two pages should feel like they came from the same template.

---

## Typography

**Principle: extreme contrast, not subtle gradation.**

| Use case | Font | Weight |
|----------|------|--------|
| Landing page display headings | Fraunces | 900 (black) |
| Landing page body / UI labels | Bricolage Grotesque | 400-600 |
| Data callouts (FL ratings, PFM codes, scientific notation, form labels, eyebrow labels) | JetBrains Mono | 400-500 |
| App headings (h1-h3) | IBM Plex Serif | 700-900 |
| App body / paragraphs | Inter | 400-600 |

Rules:
- Use weight 900 for display, 400 for body — not 600 vs 400
- Size jumps of 3x or more between display and supporting text, not 1.5x
- The defined font stack covers every need — never introduce additional families
- JetBrains Mono for **any** number, identifier, or code-like datum in the UI
- Inter is the workhorse sans-serif; IBM Plex Serif handles all in-app headings via the global `h1,h2,h3` rule in `globals.css`

---

## Colour & Theme

**Principle: one dominant colour, one sharp accent, disciplined neutrals.**

### Colour Format

All colour tokens use **oklch** (perceptually uniform) — never HSL or hex in new code. The full token set lives in `globals.css` under `@theme`. Components consume colours exclusively via Tailwind utility classes generated from those tokens.

### Surface Levels

Five distinct surface levels provide elevation-based hierarchy:

| Token | Light mode | Dark mode | Usage |
|-------|-----------|-----------|-------|
| `background` | L=0.975, warm hue 78 | L=0.145, cool hue 260 | Page background |
| `surface-1` | L=0.965 | L=0.175 | Cards, sidebars |
| `surface-2` | L=0.945 | L=0.210 | Table headers, filter bars |
| `surface-3` | L=0.920 | L=0.245 | Hover states, dropdowns |
| `surface-elevated` | L=0.995 | L=0.220 | Modals, popovers |

### Landing / Marketing Surfaces
Use the `lp-*` palette (defined in `globals.css`):

| Token | Role |
|-------|------|
| `lp-basin` | Primary dark background (#0C1A2E deep navy) |
| `lp-copper` | Primary accent — CTAs, highlights, active states |
| `lp-spillway` | Secondary accent — badges, links |
| `lp-chalk` | Light section backgrounds, display text on dark |
| `lp-steel` | Secondary / muted text |
| `lp-concrete` | Subtle dividers, inactive states |

### App Surfaces
Use standard semantic tokens: `primary`, `foreground`, `muted-foreground`, `border`, `success`, `warning`, `destructive`.

> **Note:** `surface-*` tokens (`surface-1`, `surface-2`, `surface-3`, `surface-elevated`) are defined and available for elevation-based hierarchy, but adoption is gradual. Existing `bg-card` and `bg-muted` continue to work alongside the new surface hierarchy.

### Status Token Distinction

Two separate status palettes exist for different purposes:

- **UI feedback** (`success`, `warning`, `destructive`): Form validation errors, toasts, online indicators, confirmation states. Used pervasively across ~170+ files.
- **CVD-safe risk data** (`safe`, `caution`, `danger`, `critical`): Risk assessment status, screening results, L2RA states. Designed for colour-vision-deficiency safety with distinct hues (teal 155, amber 80, red 25, deep red 15) and always paired with shape or icon for redundant encoding.

### Risk Luminance Ramp

Six tokens (`risk-negligible` through `risk-extreme`) form a perceptually uniform ramp for TRG zone fills in risk charts. In light mode, the ramp descends from L=0.85 (negligible, light) to L=0.45 (extreme, dark). In dark mode, the ramp inverts: negligible is dark (L=0.25), extreme is lighter (L=0.56). This ensures zones remain distinguishable on both backgrounds and survive greyscale printing.

### Rules
- Dark sections must be **genuinely dark** — not dark-grey-on-dark-grey
- Avoid: purple gradients, rainbow palettes, pastel washes, generic blue CTAs
- Use `lp-copper` for CTAs on landing surfaces; `primary` for CTAs in the app
- Never hardcode hex/HSL/oklch/rgba in TSX — define in `globals.css` and consume via Tailwind utilities
- Charts must use `useChartTheme()` hook to read resolved CSS custom properties — never inline colour strings in chart code. For Recharts/D3 library props that require concrete color strings, call `useChartTheme()` to get theme-aware resolved values

---

## Dark Mode

Dark mode is a first-class citizen — not an afterthought. It is activated via `data-theme="dark"` on the document root (managed by the Zustand theme store + ThemeProvider).

### Design Principles
- Neutrals shift from warm hue 78 (light) to cool hue 260 (dark)
- Surfaces use elevation-based lightness: higher elevation = lighter surface
- Primary copper lightens ~15 points (L=0.588 to L=0.700) for readability
- Status colours lighten 10-15 points to maintain contrast
- The grain texture overlay reduces opacity (`--texture-opacity: 0.015`)
- All chart components auto-adapt via `useChartTheme()` — no manual dark overrides needed

### What Must Work
Every new component, chart, badge, table, and form must look correct in both light and dark mode. Test both before considering work complete.

---

## Section Divider Pattern

The `.section-divider` CSS class is the standard horizontal separator between content sections:

```html
<div class="section-divider" />
```

It renders a 1px gradient line that fades from `stone-300` to transparent. Both light and dark modes are handled via the token overrides. Use this instead of `<hr>` or manual gradient dividers in Tailwind classes.

---

## Motion

**Principle: one orchestrated moment over scattered micro-animations.**

### Duration Tokens

| Token | Value | Use case |
|-------|-------|----------|
| `--duration-instant` | 0ms | Immediate state changes |
| `--duration-micro` | 80ms | Hover highlights, focus rings |
| `--duration-fast` | 150ms | Tooltips, dropdown appearance |
| `--duration-normal` | 280ms | Panel transitions, tab switches |
| `--duration-slow` | 450ms | Chart loading sequences |
| `--duration-deliberate` | 700ms | Page-level reveals |

### Easing Tokens

| Token | Curve | Use case |
|-------|-------|----------|
| `--ease-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Default for reveals, entries |
| `--ease-in-out` | `cubic-bezier(0.45, 0, 0.55, 1)` | Continuous motion (hover) |
| `--ease-in` | `cubic-bezier(0.55, 0, 1, 0.45)` | Exit animations |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Playful bounces (sparingly) |

### Reduced Motion

All duration tokens zero out under `prefers-reduced-motion: reduce`. Additionally, a global wildcard rule sets `animation-duration: 0.01ms` and `transition-duration: 0.01ms` on all elements. This is non-negotiable.

- **Landing page sections**: scroll-triggered reveals via IntersectionObserver with staggered `animation-delay`
- **App UI**: instant state changes; reserve motion for data loading (skeleton to content) and destructive confirmations
- **Hover states**: subtle scale or brightness shift — not colour swaps that look like bugs
- Every animation in `globals.css` **must** have a `@media (prefers-reduced-motion: reduce)` fallback

---

## Backgrounds & Spatial Composition

- Never default to a plain solid background; layer gradients, topographic patterns, or subtle geometric textures where contextually appropriate
- Use the `body::after` grain texture (already in `globals.css`) — it's free atmosphere
- Dark hero sections benefit from topographic contour lines (copper, 8-14% opacity)
- Light sections benefit from very subtle warm gradient (chalk to slightly cooler white at top)
- Decoration is the supporting cast; **charts and tables are the hero** — never let background effects reduce data legibility

---

## Components & Layout

- **Cards**: `rounded-xl` with subtle border (`border-border/50`) — not heavy drop shadows
- **Buttons**: `rounded-md`; `lp-copper` filled for primary CTA on dark; `primary` for app actions
- **Active states**: `text-lp-copper` + bottom border OR `bg-primary/15 text-primary` — not bold text alone
- **Dividers**: Use `.section-divider` for content sections; `border-border/50` for inline separators
- **Spacing**: generous — prefer padding that feels roomy over content that fills every pixel
- **Mobile**: every component must be fully usable at 375px; test compact navbars, stacked layouts

---

## What to Actively Avoid

| Anti-pattern | Why |
|---|---|
| Centered hero + gradient button | It's the default. Find a different layout. |
| Purple/lavender accents | No domain relevance. Use the engineering palette. |
| Rounded pill buttons everywhere | Engineering tools use precise rectangular shapes. |
| 3-column card grids with equal-weight cards | Too generic. Use editorial hierarchy. |
| Animations on every interaction | Fatigue. Reserve motion for key moments. |
| "Safe" grey text on white | Low personality. Use `lp-steel` or push to true black on chalk. |
| Generic stock-photo heroes | Either a product mockup or a domain-specific graphic (topography, risk matrix). |
| Hardcoded colour values in components | All colours flow from `globals.css` tokens via Tailwind. |
| Ignoring dark mode | Every surface must be verified in both themes. |
