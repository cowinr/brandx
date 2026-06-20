---
date: 2026-06-20
topic: generic-engine
---

# Generic Engine Requirements

## Summary

The generic engine is brandx's identity-free renderer: one command that turns a markdown file into either a branded HTML document or an Outlook-safe email. Every visual comes from the user's brand config, with defaults sensible enough that a fresh install produces something personal before any setup. The engine itself knows nothing about any specific person.

## Problem Frame

brandx exists to make a personal-branding renderer shareable (see STRATEGY.md). The strategy's spine is "identity is pure data, the engine is generic." This brainstorm scopes the engine half of that bet: the renderer that must hold zero person-specific knowledge so that adopting the look never means forking the code. The prior prototype (T196 / ea-brand) proved the output is worth sharing but welded identity and assets into the tool. The engine is where that entanglement gets undone.

## Key Decisions

- **Fresh visual design, not a reproduction of T196.** The engine's visual system is designed from a blank canvas rather than recreating the gradient-bar letterhead and teal styling of the prototype. This costs more design iteration but lets the system be generic from the start instead of carrying one person's choices.
- **One command, behaviour selected by flags.** A single entry point covers both surfaces and all knobs. The literal flag grammar is left to planning; this doc fixes only the set of capabilities the flags must expose.
- **Email is a graceful degradation of the document.** The two surfaces share one semantic render; the email surface drops to what Outlook can reliably display. Richer on the page, robust in the inbox.
- **The engine consumes a resolved config and computes nothing.** Brand values resolve through a four-layer cascade (application defaults, home config, frontmatter, invocation flags) owned by the Identity config track. The engine renders whatever resolved config it is handed, including zero-config personalisation (an OS-derived name, neutral palette) that the resolver produces. It holds no schema, location, or defaulting logic of its own.

## Requirements

**Output surfaces**

- R1. The engine renders a markdown file to a branded HTML document.
- R2. The engine renders a markdown file to Outlook-safe email HTML (inline styles, table-based layout, embedded assets).
- R3. The engine can open a rendered output in a browser for preview.

**Output destinations**

- R4. The engine can write rendered output to a file.
- R5. The engine can copy rendered output to the system clipboard, supporting the paste-into-Outlook workflow for the email surface.

**Invocation and identity selection**

- R6. The engine is a single command whose surface and behaviour are selected by flags.
- R7. A user can choose the identity mark (monogram or avatar). The config sets the default; an invocation-time choice overrides it for that render.
- R8. A user can point the engine at an alternate brand config, overriding the home-area default.

**Markdown feature floor**

- R9. The engine renders standard markdown: headings, lists, tables, links, images, emphasis, and blockquotes.
- R10. The engine renders a branded letterhead (identity lockup and date) composed from the config and optional frontmatter.
- R11. The engine renders GitHub-style callouts (`> [!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!IMPORTANT]`, `[!CAUTION]`) as brand-coloured blocks.
- R12. The engine renders fenced code blocks with syntax highlighting on the document surface, and as plain inline-styled monospace on the email surface.
- R13. The document surface carries a print stylesheet so it prints or saves to PDF cleanly. The email surface does not.

**Identity as pure data**

- R14. The engine holds zero person-specific values. Every identity and brand value (name, role, initials, colours, fonts, date format, avatar) is read from the resolved config, never hardcoded.
- R15. The engine renders the identity present in the resolved config and computes no defaults itself. Zero-config personalisation (an OS-derived name, neutral palette, initials monogram, no role) is produced by the Identity config resolver, not the engine.
- R16. The engine renders the resolved identity line and monogram exactly as provided. Graceful handling of a username-only OS account is the resolver's responsibility (see the Identity config doc, its R6).

**Frontmatter (all optional, all defaulted)**

- R17. Frontmatter is optional and resolves as one cascade layer above the home config. The common document keys default sensibly: `title` (falls back to the first heading), `subtitle`, `date` (defaults to today, rendered in the resolved date format), and `mark`. A file with no frontmatter still renders correctly.

## Acceptance Examples

- AE1. Covers R12. Given a markdown file with a fenced `python` code block, when rendered as a document the code is syntax-highlighted; when rendered as email the same block is plain monospace on an inline-styled background.
- AE2. Covers R15. Given a resolved config the resolver produced from no user config, the letterhead renders the OS account's full name, an initials monogram, no role, and the neutral default palette and font.
- AE3. Covers R16. Given a resolved config whose identity came from a username-only OS account, the engine renders the resolver's graceful fallback rather than `u1924` or `U1`.
- AE4. Covers R7. Given a config whose default mark is the monogram, when the user requests the avatar at invocation time the render uses the avatar for that output only.
- AE5. Covers R2, R12, R13. Given any input, the email output contains no `<style>` blocks, no class-based syntax spans, and no print stylesheet, so it survives Outlook.

## Scope Boundaries

**Deferred for later**

- RAG status colours (red/amber/green backgrounds). Cut from the v1 floor; revisit if real usage wants them.
- Printing to stdout as an output destination.

**Owned by another track**

- The brand config's schema, field set, and home-area location. Identity config track.
- Config scaffolding and first-run `init`. Install and distribution track.

**Outside the engine's identity**

- A brandx skill or any markdown-authoring logic. Any skill, tool, or person produces the markdown; the engine only applies branding.
- Batch or multiple-file input. One file per invocation.
- Syntax-highlighted code in the email surface (resolved by R12 in favour of plain monospace).

## Dependencies and Assumptions

- The engine assumes a resolved brand config produced by the Identity config track. That contract is defined in the Identity config requirements doc (`docs/brainstorms/2026-06-20-identity-config-requirements.md`).
- The visual design is produced as build-time iteration within this track (mockups reviewed and refined), not specified in this document. This doc captures behaviour; the look is designed during the work.
- OS full-name lookup is assumed available on macOS, Windows, and Linux. Where it is not, the username fallback in R16 applies.

## Outstanding Questions

**Resolved**

- The resolved-config contract (R14 depends on it) is now defined in the Identity config requirements doc, so engine planning is no longer blocked on it.

**Deferred to planning**

- Flag grammar and defaults for the single command (R6).
- Markdown renderer and syntax-highlighter library choices (R9, R12).
- Cross-platform clipboard mechanism (R5).
- Whether the document surface embeds assets (fonts, avatar) for a fully self-contained file, or links them. Leaning self-contained so a shared document needs nothing else, but confirm against file-size cost during planning.
