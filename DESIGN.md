---
name: Store & Analytics Platform
description: Precision Ledger & Living Store — Clean lifestyle e-commerce with a high-density dark telemetry console.
colors:
  primary-dark: "#1C2331"
  primary-blue: "#1E88E5"
  accent-indigo: "#3F51B5"
  terminal-blue: "#3B82F6"
  bg-light: "#F4F6F9"
  card-light: "#FFFFFF"
  dark-obsidian: "#08090A"
  dark-surface: "#111317"
  text-main: "#2C3E50"
  text-muted: "#7F8C8D"
  border-light: "#E2E8F0"
  border-dark: "#1E222B"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "clamp(2rem, 4vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
rounded:
  sm: "4px"
  sober: "6px"
  md: "10px"
  lg: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.primary-dark}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sober}"
    padding: "10px 24px"
  button-accent:
    backgroundColor: "{colors.primary-blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sober}"
    padding: "10px 24px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.primary-dark}"
    rounded: "{rounded.sober}"
    padding: "10px 20px"
  card-store:
    backgroundColor: "{colors.card-light}"
    rounded: "{rounded.sober}"
    padding: "16px"
  input-sober:
    backgroundColor: "#FFFFFF"
    textColor: "{colors.text-main}"
    rounded: "{rounded.sober}"
    padding: "10px 14px"
---

# Design System: Store & Analytics Platform

## Overview

**Creative North Star: "Precision Ledger & Living Store"**

The visual system embodies a deliberate dual-lens architecture. On the consumer storefront, the interface presents a bright, airy, and welcoming shopping experience built on crisp white surfaces, soft cool slate backgrounds, and restrained navy accents. In contrast, the executive analytics portal shifts into a dark, high-contrast, instrumental console designed for dense telemetry scanning, financial charting, and real-time operational simulation.

Surfaces remain flat and structured by default, relying on disciplined 1px borders and subtle tonal layering rather than heavy skeuomorphism. Interactive elements lift with subtle, calculated shadow transitions upon hover.

**Key Characteristics:**
- **Dual-Surface Stance:** Distinct light consumer retail space and dark command console telemetry.
- **Structural Sobriety:** Structured 6px to 10px corner radii, clean hairline strokes, and high readability.
- **Data-Dense Hierarchy:** Clear distinction between scannable metadata, pricing anchors, and interactive CTA elements.

## Colors

The color palette establishes high functional contrast across both operating modes.

### Primary
- **Deep Slate Navy** (`#1C2331`): Anchors navigation bars, footers, primary checkout actions, and structural headers across the storefront.
- **Electric Azure** (`#1E88E5`): Highlights active category links, cart indicators, focused input rings, and primary action accents.

### Secondary
- **Royal Indigo** (`#3F51B5`): Applied to badge gradients, subtle secondary highlights, and brand icon motifs.
- **Terminal Vivid Blue** (`#3B82F6`): The primary visual signal for charts, forecast metrics, and telemetry badges in the dark analytics suite.

### Neutral
- **Cool Off-White** (`#F4F6F9`): Main page canvas background for the storefront.
- **Pure White Surface** (`#FFFFFF`): Product card surfaces, form wrappers, and input backgrounds.
- **Charcoal Slate** (`#2C3E50`): High-legibility primary body text and section titles.
- **Muted Steel Gray** (`#7F8C8D`): Subtitles, helper text, and inactive metadata labels.
- **Light Border Stroke** (`#E2E8F0`): Hairline boundary between cards, rows, and input fields.
- **Dark Obsidian Canvas** (`#08090A`): Background for the executive analytics dashboard.
- **Dark Surface Panel** (`#111317`): Card panels, chart containers, and tables within the analytics portal.
- **Console Border Stroke** (`#1E222B`): Subtle grid divider across analytics widgets.

### Named Rules
**The Dual-Surface Rule.** Storefront surfaces must strictly utilize the light palette (`#F4F6F9` canvas, `#FFFFFF` cards) for consumer trust and openness. Analytics tools must utilize the dark obsidian palette (`#08090A` canvas, `#111317` containers) for focused, high-contrast data visualization.

**The Rarity Accent Rule.** Electric Azure (`#1E88E5`) and Terminal Blue (`#3B82F6`) must never cover more than 15% of a screen. Their visual punch is preserved only when reserved for CTAs, active filters, and key metrics.

## Typography

**Display Font:** System UI Stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`)
**Body Font:** System UI Stack
**Monospace / Numeric Font:** System Monospace (`ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace`)

**Character:** Modern, clean, and immediately rendered without web-font loading lag. Clear geometric sans-serif shapes ensure legibility across both consumer shopping cards and dense tabular financial grids.

### Hierarchy
- **Display** (Bold 700, `clamp(2rem, 4vw, 2.5rem)`, line-height: `1.2`): Hero banners and prominent auth titles.
- **Headline** (Bold 700, `1.5rem` / `24px`, line-height: `1.3`): Section headings, category headers, and dashboard metric titles.
- **Title** (Semi-Bold 600, `1.125rem` / `18px`, line-height: `1.4`): Product card titles, modal headings, and table grouping headers.
- **Body** (Regular 400, `0.875rem` / `14px`, line-height: `1.5`): Product descriptions, customer reviews, and general UI descriptions. Maximum line length: `65–75ch`.
- **Label / Badges** (Semi-Bold 600, `0.75rem` / `12px`, letter-spacing: `0.05em`, uppercase): Category tags, stock status badges, and table column headers.
- **Monospace Telemetry** (Medium 500, `0.8125rem` / `13px`, line-height: `1.4`): Price tags, ETL batch counts, order IDs, and simulator formulas.

### Named Rules
**The Metric Legibility Rule.** All numerical monetary values (`$ 129.99`) and analytics calculations must use dedicated tabular figures or monospace stacks to ensure vertical alignment in tables and cards.

## Layout

- **Container Widths:** Fixed-fluid grid with `max-width: 1200px` for the storefront and `max-width: 1440px` for executive analytics.
- **Spacing Scale:** Built on a 4px/8px modular rhythm (`4px`, `8px`, `16px`, `24px`, `32px`, `48px`).
- **Product Catalog Grid:** 4-column responsive layout (`col-lg-3 col-md-6 col-12`) with equal-height flex alignment (`d-flex align-items-stretch`).
- **Category Filter Rail:** Horizontal swipe-scrollable navigation bar with smooth scrolling and responsive edge arrows (`#categoryScrollWrapper`).
- **Analytics Dashboard Grid:** 12-column telemetry grid featuring high-density KPI cards on top, followed by 2-column chart splits (`col-lg-8` / `col-lg-4`).

## Elevation & Depth

Surfaces are flat-by-default with crisp 1px borders. Elevation is used strictly to communicate interactive state, layering, and temporary modals.

### Shadow Vocabulary
- **Rest Elevation** (`box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04)`): Base shadow for product cards and sober containers.
- **Hover Lift** (`box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12)`, `transform: translateY(-2px)`): Interactive feedback when hovering over product cards and avatars.
- **Elevated Modal & Auth** (`box-shadow: 0 12px 32px rgba(0, 0, 0, 0.08)`): Auth cards, floating modals, and slide-in notifications.
- **Focus Glow** (`box-shadow: 0 0 0 3px rgba(30, 136, 229, 0.15)`): Applied to active form inputs and focused buttons for accessible focus ring visibility.

### Named Rules
**The Flat-By-Default Rule.** All cards and containers sit flush with their canvas at rest. Elevation transitions must only trigger on user cursor hover, touch press, or modal focus.

## Shapes

- **Form Language:** Clean, contemporary rectangles with restrained corner rounding.
- **Corner Radii:**
  - **Sober Standard** (`border-radius: 6px`): Standard for buttons, product cards, category navigation pills, and table wrappers.
  - **Medium Card** (`border-radius: 10px`): Used for form inputs and cart summary boxes.
  - **Large Wrapper** (`border-radius: 16px`): Reserved for auth cards and floating profile containers.
  - **Circular Pill** (`border-radius: 9999px`): Used for avatar photos, quantity stepper buttons, and floating action triggers.
- **Borders:** Consistent 1px solid `#E2E8F0` on light surfaces and `#1E222B` on dark surfaces.

## Components

### Buttons
- **Shape:** Sober standard radius (`border-radius: 6px`).
- **Primary Action (`.sober-btn-primary`):** Solid Deep Slate Navy (`#1C2331`), white text, bold font weight (`600`), padding `10px 24px`. Hover shifts to `#2C3E50`.
- **Accent Action (`.btn-accent`):** Electric Azure (`#1E88E5`) or Vivid Blue (`#3B82F6`), white text, padding `8px 16px`.
- **Outline Action (`.sober-btn-outline`):** Transparent background with 1px solid `#E2E8F0`, dark text (`#2C3E50`), padding `10px 20px`. Hover shifts to `#F8F9FA` background.
- **Quantity Stepper (`.cart-qty-btn`):** 32px × 32px circular button (`50%` radius), 1px border, centered bold glyph.

### Cards & Containers
- **Product Card:** Light surface (`#FFFFFF`), sober radius (`6px`), 1px light border (`#E2E8F0`), image box height (`200px`) with clean containment (`object-fit: contain`).
- **Analytics KPI Card:** Dark surface (`#111317`), 1px dark border (`#1E222B`), top accent indicator, large monospace metric readout with micro trend indicators.

### Inputs & Form Fields
- **Sober Input (`.sober-input`):** White background, 1px border (`#E2E8F0`), radius `6px`, padding `10px 14px`. Focus transitions to border `#1E88E5` with `0 0 0 3px rgba(30, 136, 229, 0.15)` ring.
- **Form Label:** Upper-case, 12px, bold (`600`), muted slate color (`#2C3E50`), letter-spacing `0.5px`.

### Badges & Chips
- **Category Badge:** Soft gray background, 1px border, muted text, padding `2px 8px`, radius `4px`.
- **Brand Badge:** Solid primary blue (`#1E88E5`), crisp white text, padding `2px 8px`, radius `4px`.
- **Analytics Telemetry Pill (`.badge-restricted`):** 10px uppercase, letter-spacing `0.05em`, 1px solid `#1E222B`, text `#64748B`.

### Navigation
- **Storefront Navbar:** Fixed top, white background with subtle shadow, dark bold links, category horizontal scroller below.
- **Analytics Navbar:** Dark obsidian background (`#08090A`), 1px bottom border (`#1E222B`), active bottom border tab (`border-bottom: 2px solid #3B82F6`).

## Do's and Don'ts

### Do:
- **Do** maintain the clean light theme for all customer shopping views (`/`, `/product/`, `/checkout/`, `/orders/`) and the dark console theme for `/analytics/`.
- **Do** preserve the 6px sober border radius on standard cards, buttons, and badges.
- **Do** keep product images centered on neutral `#FAFAFA` containers with `object-fit: contain`.
- **Do** ensure all numerical currency prices and quantitative metrics use tabular, high-contrast typography.
- **Do** provide smooth keyboard focus rings (`0 0 0 3px rgba(30, 136, 229, 0.15)`) on all interactive inputs and buttons.

### Don't:
- **Don't** mix dark mode containers inside the storefront shopping catalog or bright white panels inside the analytics dashboard.
- **Don't** use excessive shadows or deep blurs at rest; keep surfaces flat and lift only on hover.
- **Don't** allow horizontal scroll overflows on mobile; use smooth scrolling wrappers with hidden scrollbars for long pill lists.
- **Don't** use saturated bright colors for generic text; stick strictly to `#2C3E50` and `#7F8C8D` on light and `#F8FAFC` and `#64748B` on dark.
