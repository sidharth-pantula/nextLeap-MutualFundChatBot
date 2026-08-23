---
name: Obsidian Verity
colors:
  surface: '#0f131c'
  surface-dim: '#0f131c'
  surface-bright: '#353942'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#dfe2ee'
  on-surface-variant: '#bacac1'
  inverse-surface: '#dfe2ee'
  inverse-on-surface: '#2c3039'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#4fdbc8'
  on-secondary: '#003731'
  secondary-container: '#04b4a2'
  on-secondary-container: '#003f38'
  tertiary: '#ffc8a3'
  on-tertiary: '#502500'
  tertiary-container: '#ffa15b'
  on-tertiary-container: '#733800'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#71f8e4'
  secondary-fixed-dim: '#4fdbc8'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005048'
  tertiary-fixed: '#ffdcc6'
  tertiary-fixed-dim: '#ffb785'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#713700'
  background: '#0f131c'
  on-background: '#dfe2ee'
  surface-variant: '#31353e'
  surface-slate: '#1E293B'
  border-subtle: '#334155'
  warning-amber: '#F59E0B'
  text-muted: '#94A3B8'
  groww-classic: '#00B386'
typography:
  headline-xl:
    fontFamily: Outfit
    fontSize: 40px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  nav-value:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 24px
  container-max: 1280px
---

## Brand & Style

The design system is built for a "Facts-Only" RAG (Retrieval-Augmented Generation) fintech application. It prioritizes precision, speed, and institutional-grade clarity. The brand personality is clinical yet approachable—stripping away financial jargon in favor of verified, data-driven insights.

The visual style is a **Modern Glassmorphic** evolution of the Groww aesthetic. It utilizes a deep, multi-layered dark mode to reduce cognitive load during heavy data analysis. Key characteristics include:
- **Depth through Transparency:** Using frosted glass effects to create a sense of hierarchy without heavy shadows.
- **Precision Accents:** Using vibrant emerald and teal glows to highlight actionable intelligence and verified "facts."
- **Institutional Rigor:** High-contrast typography and a 1px border language that feels engineered and secure.

## Colors

The palette is anchored in **Deep Obsidian (#0B0F17)**, providing a high-contrast foundation for data density. 

- **Primary Actions:** Groww Emerald (#00D09C) is reserved for the most critical user actions (Buy, Confirm, Primary CTA). 
- **System Accents:** Teal Glow (#14B8A6) is used for secondary data visualizations, verified checkmarks, and focus states.
- **Surface Tiers:** Backgrounds transition from Obsidian to Slate (#1E293B) to define hierarchy.
- **Guardrails:** Warning Amber (#F59E0B) is strictly used for RAG "hallucination" warnings or financial risk notifications. 
- **Borders:** A consistent 1px Slate (#334155) is used for all containment to maintain a sharp, technical feel.

## Typography

This design system uses a dual-font approach to separate narrative from data:

1.  **Outfit (Headlines):** A geometric sans-serif that brings a modern, fintech-forward energy. Used for all page titles and card headers.
2.  **Inter (Body):** Selected for its exceptional legibility in dense financial tables and conversational RAG outputs.
3.  **JetBrains Mono (Utility):** Crucial for "Facts-Only" reliability. Used for timestamps, NAV values, percentage changes, and source citations.

All typography in the "Deep Obsidian" mode should use a primary white (#FFFFFF) for titles and "Slate 400" (#94A3B8) for secondary body text to ensure optical comfort.

## Layout & Spacing

The system follows a strict **8px grid system** for consistent vertical rhythm.

- **Layout Model:** A 12-column fluid grid for desktop with 24px gutters. For the dashboard and RAG chat interface, a fixed-sidebar (280px) with a fluid content area is preferred.
- **RAG Chat Density:** Chat bubbles and data cards use 16px (md) internal padding to maintain focus.
- **Breakpoints:**
  - **Mobile (<768px):** Single column, 16px side margins.
  - **Tablet (768px - 1024px):** 8-column grid, 20px margins.
  - **Desktop (>1024px):** 12-column grid, 24px margins, 1280px max-width container.

## Elevation & Depth

Depth is achieved through **Glassmorphism and Tonal Layering** rather than traditional drop shadows.

1.  **Level 0 (Base):** Deep Obsidian (#0B0F17) solid background.
2.  **Level 1 (Cards/Containers):** Slate (#1E293B) at 60% opacity with a `backdrop-blur-md` (12px-16px blur) and a 1px border (#334155).
3.  **Level 2 (Hover States/Modals):** Increased opacity (80%) and a secondary "inner glow" 1px border using Teal Glow (#14B8A6) at 20% opacity.
4.  **Shadows:** When necessary, use extremely large, soft ambient glows (0px 20px 40px) using the Primary Emerald color at 5% opacity to "lift" the card toward the user.

## Shapes

The design system uses a **Rounded (2)** logic to soften the technical nature of fintech data. 

- **Cards & Modals:** Always use `rounded-2xl` (16px) for a premium, modern feel.
- **Buttons & Pills:** Use `rounded-lg` (8px) for buttons, while status chips/pills use a full `rounded-full` (999px) to distinguish them from actionable buttons.
- **Input Fields:** `rounded-lg` (8px) to maintain a crisp, functional appearance.

## Components

### Interactive Scheme Cards
Cards must feature a `backdrop-blur-md` background. The header includes the fund logo (circular) and an Outfit Headline-MD title. The footer of the card should use JetBrains Mono for the NAV value and return percentages, color-coded (Emerald for gain, Red for loss).

### Conversational Chat Bubbles
- **User Bubbles:** Right-aligned, Slate background, 1px Slate border.
- **System (RAG) Bubbles:** Left-aligned, Obsidian background, subtle Teal left-accent border. Facts within the bubble should be highlighted using a 10% Teal Glow background tint.

### Data-Dense Comparison Tables
Tables use 1px horizontal dividers only (#334155). Header rows use `label-mono` typography. Every second row should have a 5% Slate tint for readability (zebra striping).

### Interactive Pills/Chips
Used for filtering "Facts" vs "Speculation." Active states use a solid Teal Glow with Obsidian text. Inactive states use a 1px Slate border with White text.

### Input Fields
Dark backgrounds (#0B0F17) with a 1px Slate border. On focus, the border transitions to Primary Emerald with a 4px outer glow of the same color at 15% opacity.