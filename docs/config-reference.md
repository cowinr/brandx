# brandx config reference

This document is generated from the application defaults source (`brandx.config.defaults`).
Do not edit manually — regenerate with `brandx docsgen` after changing defaults.

Keys are shown in their YAML dotted-path form.
Nested blocks (e.g. `colours`) contain multiple keys; override any key individually.

## `identity`

**`identity.name`**

Default: *(empty)*

Displayed in the document/email letterhead and used to derive the monogram. When absent at every config layer the resolver reads the OS full name or title-cases the login username.

*Config comment: Your full name — leave blank to use your OS account name.*

---

**`identity.role`**

Default: ``

Letterhead role line. Leave blank to omit the role from the letterhead.

*Config comment: Your job title or role line shown beneath your name in the letterhead.*

---

**`identity.avatar`**

Default: *(empty)*

Used in the letterhead when mark is set to 'avatar'. Relative paths resolve from the document's directory.

*Config comment: Path to an avatar image (PNG/JPEG). Leave blank to use the monogram.*

---

**`identity.avatar_email`**

Default: *(empty)*

Optional email-specific avatar (typically a smaller crop). When absent, the main avatar is used for both surfaces.

*Config comment: Path to a smaller avatar for email letterheads. Falls back to avatar.*

---

**`identity.mark`**

Default: `monogram`

Selects the letterhead mark. 'monogram' shows derived initials; 'avatar' shows the image.

*Config comment: Identity mark style: 'monogram' (default) or 'avatar'.*

---

## `colours`

**`colours.blue`**

Default: `#1c2b39`

Used for primary heading and structural elements across both surfaces.

*Config comment: Primary dark colour — headings, table headers, letterhead text.*

---

**`colours.blue_light`**

Default: `#0d8a7d`

Paired with 'blue' for the gradient bar and role text.

*Config comment: Secondary accent — role line, heading underlines, links.*

---

**`colours.accent`**

Default: `#0d8a7d`

Used for accent borders on plain blockquotes and the letterhead gradient.

*Config comment: Accent colour — blockquote bars, active UI elements.*

---

**`colours.important`**

Default: `#b07514`

Callout bar and label colour for the IMPORTANT alert type.

*Config comment: Amber tone for [!IMPORTANT] callout bars and labels.*

---

**`colours.grey_900`**

Default: `#1f2933`

Primary body text colour on both surfaces.

*Config comment: Near-black body text.*

---

**`colours.grey_700`**

Default: `#46535f`

Used inside callouts and blockquotes where a slightly lighter tone aids hierarchy.

*Config comment: Secondary body text — callout bodies, blockquote prose.*

---

**`colours.grey_500`**

Default: `#7c8893`

Date and footer text in the letterhead.

*Config comment: Muted text — dates, captions, footer.*

---

**`colours.grey_200`**

Default: `#e2e8ec`

Table row dividers, code-block borders, section rules.

*Config comment: Divider and border colour.*

---

**`colours.grey_50`**

Default: `#f4f7f8`

Alternate table row fill and code-block background on the document surface.

*Config comment: Subtle surface background — code blocks, alternate table rows.*

---

**`colours.rag_green_bg`**

Default: `#e8f5ed`

Alert background — TIP callout and green RAG status cells.

*Config comment: Background fill for [!TIP] and RAG-green cells.*

---

**`colours.rag_green_text`**

Default: `#2a7f4f`

Alert label and bar colour for TIP callouts.

*Config comment: Text/bar colour for [!TIP] and RAG-green cells.*

---

**`colours.rag_amber_bg`**

Default: `#fdf3e3`

Alert background — WARNING callout and amber RAG status cells.

*Config comment: Background fill for [!WARNING] and RAG-amber cells.*

---

**`colours.rag_amber_text`**

Default: `#b07514`

Alert label and bar colour for WARNING callouts.

*Config comment: Text/bar colour for [!WARNING] and RAG-amber cells.*

---

**`colours.rag_red_bg`**

Default: `#fce8e8`

Alert background — CAUTION callout and red RAG status cells.

*Config comment: Background fill for [!CAUTION] and RAG-red cells.*

---

**`colours.rag_red_text`**

Default: `#b33a3a`

Alert label and bar colour for CAUTION callouts.

*Config comment: Text/bar colour for [!CAUTION] and RAG-red cells.*

---

**`colours.note_bg_html`**

Default: `#e6f4f2`

NOTE callout background on the document renderer.

*Config comment: Background fill for [!NOTE] on the document surface.*

---

**`colours.note_bg_email`**

Default: `#e6f4f2`

NOTE callout background on the email renderer. May differ from note_bg_html.

*Config comment: Background fill for [!NOTE] on the email surface.*

---

**`colours.important_bg_html`**

Default: `#fdf3e3`

IMPORTANT callout background on the document renderer.

*Config comment: Background fill for [!IMPORTANT] on the document surface.*

---

**`colours.important_bg_email`**

Default: `#fdf3e3`

IMPORTANT callout background on the email renderer.

*Config comment: Background fill for [!IMPORTANT] on the email surface.*

---

**`colours.table_hover`**

Default: `#e9f3f1`

Hover state for table rows on the document surface.

*Config comment: Table row hover fill (document only; emails ignore :hover).*

---

## `fonts`

**`fonts.family`**

Default: `'Inter', -apple-system, 'Segoe UI', Arial, sans-serif`

Applied via CSS variable on the document renderer.

*Config comment: CSS font-family stack for the document surface.*

---

**`fonts.family_email`**

Default: `'Inter', 'Segoe UI', Arial, Helvetica, sans-serif`

Inline-styled on every element in the email renderer. Email clients cannot load web fonts; this stack relies on system fonts.

*Config comment: CSS font-family stack for the email surface (web-safe only).*

---

**`fonts.google_url`**

Default: `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap`

Loaded via <link> in the document renderer. Not used in email; the email stack is web-safe only.

*Config comment: Google Fonts URL for the document surface web font. Set to empty to skip.*

---

## `date`

**`date.format`**

Default: `long-british`

Controls how the document/email date is rendered in the letterhead.

*Config comment: Date display format. Named formats: 'long-british' (8 April 2026), 'iso' (2026-04-08), 'us' (April 8, 2026), 'eu' (08.04.2026). Or a strftime pattern, e.g. '%%d/%%m/%%Y'.*

---
