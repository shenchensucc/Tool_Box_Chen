# Design System — Chen's Engineer Toolbox

## Product Context
- **What this is:** A Streamlit + FastAPI web application for pipeline and facility integrity engineers
- **Who it's for:** Pipeline engineers, corrosion engineers, integrity analysts — people who live in Excel and trust numbers
- **Space/industry:** Pipeline integrity management, ILI data analysis, dig package generation
- **Project type:** Internal engineering tool / web app

## Aesthetic Direction
- **Direction:** Industrial-Precision
- **Decoration level:** Minimal — typography and color hierarchy carry everything, no decoration for its own sake
- **Mood:** A Garmin avionics display crossed with a modern developer tool. Precise, legible, purposeful. Makes the engineer feel in control of complex data. Zero fluff.
- **What we are NOT:** Generic SaaS purple gradients, bubbly rounded corners, stock-photo hero sections

## Typography
- **Primary UI / Body:** DM Sans — clean geometric sans, excellent at small data-dense sizes, not overused
- **Numbers, IDs, Chainages, Code:** JetBrains Mono — engineers subconsciously trust monospaced data; all chainage values, feature IDs, and numeric fields use this
- **Loading:** Google Fonts CDN
  ```html
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  ```
- **Scale:**
  - Hero/h1: 2.2rem, weight 700
  - Section/h2: 1.5rem, weight 600
  - Subsection/h3: 1.15rem, weight 600
  - Body: 0.95rem, weight 400, line-height 1.6
  - Caption/label: 0.825rem, weight 500, letter-spacing 0.03em, uppercase
  - Monospace data: 0.875rem, weight 500

## Color
- **Approach:** Restrained — petroleum blue dominates, amber is rare and meaningful (only for primary CTAs and critical warnings)
- **Primary:** `#0F3460` — deep petroleum blue, signals precision, trust, technical depth
- **Primary hover/light:** `#1A4A7A`
- **Accent / CTA:** `#F59E0B` — amber, used ONLY for primary action buttons and critical data highlights. Rare = powerful.
- **Accent hover:** `#D97706`
- **Background (light):** `#F8FAFC` — barely-off-white, easy on the eyes during long sessions
- **Surface:** `#FFFFFF`
- **Surface raised:** `#F1F5F9` — card backgrounds, metric boxes
- **Border:** `#E2E8F0` — subtle, 1px
- **Text primary:** `#0F172A`
- **Text secondary:** `#475569`
- **Text muted:** `#94A3B8`
- **Neutrals range:** `#F8FAFC` (lightest) → `#E2E8F0` → `#CBD5E1` → `#94A3B8` → `#64748B` → `#475569` → `#334155` → `#1E293B` → `#0F172A` (darkest)
- **Semantic:**
  - Success: `#059669` (engineering green, not lime)
  - Warning: `#D97706` (amber, same family as accent)
  - Error: `#DC2626` (red, unambiguous)
  - Info: `#0369A1` (technical blue, distinct from primary)
- **Sidebar:** `#1E293B` background, `#F1F5F9` text, `#F59E0B` active indicator

## Spacing
- **Base unit:** 4px
- **Density:** Comfortable-to-compact (engineers scan data, not read prose; tighter than consumer apps)
- **Scale:** 2xs(2px) xs(4px) sm(8px) md(16px) lg(24px) xl(32px) 2xl(48px) 3xl(64px)

## Layout
- **Approach:** Grid-disciplined — strict column alignment, consistent padding, no asymmetry
- **Max content width:** 1400px
- **Border radius:**
  - sm: 4px (badges, small pills)
  - md: 6px (buttons, inputs, cards)
  - lg: 8px (containers, panels)
  - Never full/pill for anything except status indicators

## Motion
- **Approach:** Minimal-functional — only transitions that aid comprehension
- **Easing:** ease-out for enter, ease-in for exit
- **Duration:** micro(100ms) short(200ms) — hover states only
- **No entrance animations, no scroll effects** — data tools need immediacy

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-31 | Deep petroleum blue primary, amber accent | Category uses generic blue/gray — this is more distinctive and signals precision engineering equipment |
| 2026-03-31 | JetBrains Mono for all numeric data | Engineers trust monospace for data; improves scanability of chainage values and feature IDs |
| 2026-03-31 | DM Sans for UI text | Not overused like Inter; clean at small sizes for data-dense layouts |
| 2026-03-31 | Amber ONLY for primary CTA and critical alerts | Scarcity = signal strength; when amber appears, the engineer knows it matters |
| 2026-03-31 | Tight 1px rule dividers, not thick `---` separators | Looks like precision instrument panels; matches the industrial aesthetic |
