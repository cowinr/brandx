---
date: 2026-06-20
topic: identity-config
---

# Identity Config Requirements

## Summary

The Identity config track defines the brand config a user owns and the resolver that turns it into the single resolved config the generic engine reads. Brand values resolve through one uniformly-named key namespace across four layers (application defaults, home-area YAML config, document frontmatter, invocation flags), each layer overriding the one below, with derivations applied for any value left absent.

## Problem Frame

The strategy's spine is "identity is pure data." That data needs a concrete home and a deterministic way to resolve it, otherwise the generic engine has nothing well-defined to render. This track supplies both: the file a user edits, and the resolution rules that always yield a complete config for the engine. It is the sibling of the Generic engine track, which depends on the resolved-config contract defined here.

## Key Decisions

- **Uniform four-layer cascade over one key namespace.** Application defaults, then home-area config, then frontmatter, then invocation flags, each overriding the one below by identical key names. Chosen for mechanical simplicity: one resolution rule for every key, no special cases. A consequence is that brand values (even a colour) can be overridden in frontmatter or by a flag. That is expected to be rare, and may serve a use case not yet foreseen, but special-casing which keys may override would cost more than it saves.
- **Full palette, every key optional and defaulted.** The complete default set lives in the application-defaults layer, so a sparse or absent user config still resolves to something usable.
- **YAML for home config and frontmatter; flags mirror the key names.** Comments to label the palette, one parser shared with frontmatter, and clean overrides by identical naming.
- **The resolver owns all defaulting and derivation.** Initials and monogram from the name, the name from the OS account when none is set, and the username fallback all happen here. The engine consumes a complete resolved config and computes nothing itself.
- **No image processing.** Avatars are supplied already prepared and embedded as-is; an optional per-surface email avatar and a heavy-image warning cover the email-weight cost.

## Requirements

**The cascade**

- R1. Brand values resolve through four layers, lowest to highest: application defaults, home-area config, document frontmatter, invocation flags.
- R2. Keys are identically named at every layer. A key present at a higher layer overrides the same key at every lower layer; keys absent at a layer fall through to the layer below.
- R3. The application-defaults layer provides a value for every key, so resolution yields a complete config even with no home config, no frontmatter, and no flags.
- R4. Home config and frontmatter share one YAML key shape; invocation flags mirror the same key names. Flag grammar is deferred to planning.

**The resolved config (contract with the engine)**

- R5. The resolver produces one complete resolved config, and that is the only brand input the engine reads (satisfies the engine's R14).
- R6. The resolver applies derivations for absent values: initials and monogram from the name; the name from the OS account when no name is set at any layer; a graceful fallback when the OS exposes only a username rather than a full name.
- R7. Avatar references in the resolved config point at images the engine can read. When the optional email avatar is absent, the resolver falls the email surface back to the main avatar.

**Home config: location and discovery**

- R8. The default home location is `~/.config/brandx/` (honouring `XDG_CONFIG_HOME`) on macOS and Linux, and `%APPDATA%\brandx\` on Windows, holding the YAML config and the avatar image(s).
- R9. Config resolution order is: explicit `--brand PATH`, then the `BRANDX_CONFIG` environment variable, then the default home location.
- R10. A missing home config is not an error. Resolution proceeds from the application defaults plus derivations.

**Schema and values**

- R11. The config exposes the full brand surface: identity (name, role, initials), the colour palette, fonts, date format, and avatar(s). Every key is optional.
- R12. Fonts resolve to a family with a fallback stack, an optional web-font URL for the document surface, and a web-safe fallback for email. All are defaulted.
- R13. Date format is a config value with a default; the engine renders dates in the resolved format. The format representation is deferred to planning.
- R14. Avatars are a main image plus an optional smaller email image, both supplied already prepared and embedded as-is. brandx performs no resizing or cropping.

**Validation behaviour**

- R15. Missing keys take their default. An unknown key produces a warning, not an error. A malformed config file produces a clear error identifying the problem.
- R16. brandx warns when an embedded avatar is large enough to bloat email output.

## Acceptance Examples

- AE1. Covers R1, R2. Given `accent` set in the home config and a different `accent` in one document's frontmatter, that document renders with the frontmatter accent while other documents keep the home-config accent.
- AE2. Covers R3, R10. Given no home config, no frontmatter, and no flags, resolution yields a complete config from application defaults plus derivations, and rendering succeeds.
- AE3. Covers R6. Given a home config with no name and an OS account full name "Ada Lovelace", the resolved name is "Ada Lovelace" and the monogram is "AL".
- AE4. Covers R6. Given an OS account exposing only the username `u1924` and no name set at any layer, the resolved identity uses the graceful fallback rather than `u1924` or `U1`.
- AE5. Covers R7, R14, R16. Given a main avatar and no email avatar, the email surface reuses the main avatar; if that image is large, brandx emits a size warning.
- AE6. Covers R9. Given `BRANDX_CONFIG` pointing at one file and `--brand PATH` passed on the call, the `--brand` file wins.

## Scope Boundaries

**Owned by another track**

- Rendering the resolved values into HTML or email. Generic engine track.
- Config scaffolding, `init`, and any first-run wizard. Install and distribution track.

**Outside this track's identity**

- Image processing or resizing of avatars. Chosen out to keep brandx dependency-light.
- Multiple named brand profiles or profile switching. Point `--brand` at different files instead.

## Dependencies and Assumptions

- The Generic engine consumes the resolved config defined here (engine R14). The two docs must agree: the engine doc is updated so that defaulting and derivation (including the OS-name fallback) are owned by this resolver, and so that the uniform cascade supersedes the engine's earlier exclusion of per-invocation value overrides.
- OS full-name lookup is assumed available on macOS, Windows, and Linux. Where it is not, the username fallback in R6 applies. This assumption is shared with the engine track.
- YAML parsing is shared between the home config and document frontmatter.

## Outstanding Questions

**Deferred to planning**

- The concrete palette key list and naming, seeded from the prototype's `brand.json` (identity, primary/accent/important, greys, callout backgrounds, link, hover).
- The flag grammar mirroring the key names.
- The date-format representation (a strftime pattern versus a small set of named formats).
- The heavy-avatar warning threshold.
