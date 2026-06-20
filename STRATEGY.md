---
name: brandx
last_updated: 2026-06-20
---

# brandx Strategy

## Target problem

A personal-branding renderer already works well (ea-brand / T196), but its identity and assets are welded into the code and it installs only on one person's machine, so it can't be handed to anyone else. There's no acute pain to relieve — this is purely a reuse and shareability problem.

## Our approach

Identity is pure data; the engine is generic. The renderer holds zero person-specific knowledge — initials, name, role, colours, fonts, date format, and avatar all live in a user-owned config in their home area. Defaults for every field mean it produces sensible branded output before any configuration, and frontmatter only ever supplements. Built fresh, not forked from the ea-brand Python.

## Who it's for

**Primary:** A person who writes markdown and wants it to carry their own brand, not their employer's and not someone else's. Comfortable running a `uv` install and editing a config file. They're hiring brandx to make their markdown look like *them* — as a document or an Outlook-safe email — without forking anyone's code.

## Key metrics

- **Zero-code adoption** — a new user goes from `uv` install to correctly-branded output editing only the config, no code edits. The core proof the data/engine separation holds.
- **Engine purity** — count of person-specific values hardcoded in the engine. Target 0; regresses the moment an identity assumption leaks back into code.
- **Zero-config sanity** — a fresh install with no config still produces clean, sensible branded output (defaults working).
- **Outlook fidelity** — email output renders correctly in Outlook, holding the bar T196 already set as the engine generalises.

## Tracks

### Generic engine

The identity-free renderer: markdown to branded HTML document and Outlook-safe email, every visual driven by config, all features defaulted.

_Why it serves the approach:_ It is the "engine is generic" half made real, and it inherits T196's Outlook fidelity as a non-negotiable constraint.

### Identity config

The brand schema that is the pure data — initials, name, role, colours, fonts, date format, avatar — where it lives in the user's home area, how the engine discovers it, and a default for every field.

_Why it serves the approach:_ It is the "identity is pure data" half; without it, identity leaks back into the engine.

### Install & distribution

`uv`-installable packaging, a clean first run (scaffold a starter config, sensible output immediately), and the docs a technical stranger needs to adopt it.

_Why it serves the approach:_ It is what turns "works for Richard" into "shareable by anyone."

## Not working on

- A brandx skill or any markdown-authoring logic. Any skill, tool, or person produces the markdown; brandx only applies branding. Owning markdown creation would be arbitrary overlay.
- A verbatim fork of the ea-brand Python. brandx is built fresh so identity assumptions don't come along for the ride.
- Non-technical onboarding (one-click installers, wizards). The primary user can run a `uv` install; "anyone" stays an aspiration, not a design driver.
