---
name: Institutional Trust System
colors:
  surface: '#0b1326'
  surface-dim: '#0b1326'
  surface-bright: '#31394d'
  surface-container-lowest: '#060e20'
  surface-container-low: '#131b2e'
  surface-container: '#171f33'
  surface-container-high: '#222a3d'
  surface-container-highest: '#2d3449'
  on-surface: '#dae2fd'
  on-surface-variant: '#c2c6d6'
  inverse-surface: '#dae2fd'
  inverse-on-surface: '#283044'
  outline: '#8c909f'
  outline-variant: '#424754'
  surface-tint: '#adc6ff'
  primary: '#adc6ff'
  on-primary: '#002e6a'
  primary-container: '#4d8eff'
  on-primary-container: '#00285d'
  inverse-primary: '#005ac2'
  secondary: '#44e2cd'
  on-secondary: '#003731'
  secondary-container: '#03c6b2'
  on-secondary-container: '#004d44'
  tertiary: '#ffb95f'
  on-tertiary: '#472a00'
  tertiary-container: '#ca8100'
  on-tertiary-container: '#3e2400'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc6ff'
  on-primary-fixed: '#001a42'
  on-primary-fixed-variant: '#004395'
  secondary-fixed: '#62fae3'
  secondary-fixed-dim: '#3cddc7'
  on-secondary-fixed: '#00201c'
  on-secondary-fixed-variant: '#005047'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#0b1326'
  on-background: '#dae2fd'
  surface-variant: '#2d3449'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
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
  label-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 24px
  margin: 24px
---

## Brand & Style

The design system is engineered for a professional fintech environment where trust and objectivity are paramount. It avoids the frantic visual noise of trading terminals in favor of a calm, scholarly, and authoritative interface. The aesthetic is **Corporate Modern** with a lean toward **Minimalism**, ensuring that the educational content—financial FAQs and compliance data—remains the focal point.

The target audience consists of Indian investors seeking clarity and reliability. The UI evokes a sense of "digital vault" security through deep, stable tones and precise alignment. 

- **Focus:** Clarity, regulatory compliance, and readability.
- **Atmosphere:** Intellectual, safe, and objective.
- **Visual Strategy:** High-contrast text on deep surfaces, utilizing color strictly for semantic meaning rather than decoration.

## Colors

The palette is anchored in a professional dark-mode spectrum that prioritizes long-form reading comfort and hierarchical clarity.

- **Background:** A stable `#0F172A` (Very dark navy) provides a grounded foundation.
- **Surface:** `#1E293B` (Deep slate) is used for cards and chat containers to create subtle depth.
- **Primary (Trust Blue):** `#3B82F6` is the primary action color, used for interactive elements and brand identifiers.
- **Secondary (Teal):** `#2DD4BF` is reserved for informative accents, such as source citations, progress indicators, and verified status marks.
- **Warning (Amber):** `#F59E0B` is strictly for compliance notices and regulatory banners.
- **Refusal (Maroon/Rose):** For system denials or out-of-scope queries, use a `#451225` background with `#FDA4AF` text to clearly signal a boundary without being aggressive.
- **Typography:** Primary content uses `#F8FAFC` (Slate-50) for maximum legibility; metadata and secondary labels use `#94A3B8` (Slate-400).

## Typography

This design system utilizes **Inter** exclusively to maintain a systematic, utilitarian aesthetic. The type scale is optimized for information density and clarity.

- **Headlines:** Use tighter letter spacing and heavier weights to establish a strong hierarchy.
- **Body Text:** Leading is generous (1.5x) to prevent eye fatigue during reading of complex financial documents.
- **Labels:** Use medium weights and subtle tracking for better scannability in data-heavy views.
- **Mobile Adjustments:** Large headlines scale down for mobile to prevent awkward line breaks while maintaining impact.

## Layout & Spacing

The design system employs a strict **8px grid** to ensure mathematical harmony across all components.

- **Layout Model:** A **fixed-width central container** (max 1200px) is preferred for the desktop experience to maintain readable line lengths for educational content. 
- **Grid:** On desktop, a 12-column grid with 24px gutters is used. On mobile, this collapses to a single-column layout with 16px side margins.
- **Chat Layout:** The assistant's conversation thread uses a staggered layout. User messages are right-aligned with the Primary color; assistant responses are left-aligned on the Surface color.
- **Spacing Rhythm:** Consistent use of 24px (lg) for section spacing and 16px (md) for internal card padding ensures a balanced, professional rhythm.

## Elevation & Depth

This design system uses a combination of **Tonal Layers** and **Low-contrast outlines** to define hierarchy, avoiding heavy shadows to keep the interface clean and "flat-modern."

- **Level 0 (Background):** `#0F172A` – The lowest plane.
- **Level 1 (Cards/Bubbles):** `#1E293B` – Used for the main UI containers. They feature a 1px border of `#334155` (Slate-700) to separate them from the background.
- **Level 2 (Modals/Popovers):** `#1E293B` with a subtle `0 10px 15px -3px rgba(0, 0, 0, 0.5)` shadow and a slightly brighter border (`#475569`).
- **Interaction:** On hover, interactive cards may increase their border-color brightness rather than adding shadow, maintaining the "factual" and "sturdy" feel of the UI.

## Shapes

The shape language is varied to distinguish between structural elements and conversational elements.

- **Structural Elements:** Cards, input fields, and containers use a **12px (Rounded)** radius. This provides a modern, approachable feel while remaining professional.
- **Conversational Bubbles:** User and AI message bubbles use a larger **24px** radius to emphasize the "chat" nature of the assistant.
- **Interactive Tags/Citations:** Buttons, chips, and labels use a **Pill-shaped (999px)** radius to maximize their identity as distinct interactive units.

## Components

### Buttons
- **Primary:** Filled Primary Blue (`#3B82F6`) with white text. Pill-shaped.
- **Secondary:** Outlined with Slate-700, Primary Blue text. Pill-shaped.

### Chat Bubbles
- **User:** Primary Blue background, white text. Bottom-right corner is 4px radius, all others are 24px.
- **Assistant:** Surface Slate background (`#1E293B`), white text. Bottom-left corner is 4px radius, all others are 24px.

### Cards
- Background: `#1E293B`.
- Border: 1px solid `#334155`.
- Radius: 12px.
- Padding: 24px.

### Input Fields
- Background: `#0F172A`.
- Border: 1px solid `#334155`.
- Radius: 12px.
- Focus: 1px solid Primary Blue with a subtle blue outer glow.

### Citations & Chips
- Background: Transparent with a 1px Teal border (`#2DD4BF`).
- Text: Teal (`#2DD4BF`).
- Radius: Pill.
- Font: Label-sm.

### Compliance Banners
- Background: Translucent Amber (`rgba(245, 158, 11, 0.1)`).
- Border: Left-edge 4px solid Amber (`#F59E0B`).
- Text: White.