---
date: 2026-06-20
topic: install-distribution
---

# Install and Distribution Requirements

## Summary

The Install and distribution track makes brandx adoptable by someone who is not the author: installable from the public Git repo with `uv`, a `brandx init` that scaffolds a commented starter config, MIT-licensed, with the docs a technical stranger needs to reach first useful output.

## Problem Frame

The engine and config tracks define behaviour; this track defines how a stranger gets brandx onto their machine and to a first branded output. Without it, the other two tracks are unreachable by anyone but the author, and the strategy's "shareable" goal goes unmet. The primary user is comfortable running a `uv` install, so the bar is a clean install path and a self-explanatory first run, not a packaged app or a wizard.

## Key Decisions

- **Git-first distribution, PyPI deferred.** brandx installs straight from the public repo so it is adoptable now with no release pipeline. The cleaner `uv tool install brandx` waits until adoption warrants the PyPI overhead.
- **Explicit `brandx init`, no auto-scaffold.** Scaffolding is a deliberate command, never a side effect of rendering, so the filesystem only changes when asked.
- **One source for the defaults.** The `init` template and the config-reference docs both derive from the application-defaults layer rather than being hand-maintained, so they cannot drift from the code.
- **MIT licence.** The simplest permissive default for a give-away tool.
- **Update by reinstall while Git-first.** With no versioned releases yet, the update path is reinstalling the latest main via `uv`.

## Requirements

**Installation**

- R1. brandx installs from the public Git repo with a single `uv` command (`uv tool install git+<repo>`), requiring no PyPI account or release pipeline.
- R2. Installation places a `brandx` command on PATH via a console entry point.
- R3. Installation works on macOS, Windows, and Linux.

**First-run scaffolding**

- R4. `brandx init` writes a starter brand config to the default home location (`~/.config/brandx/` or `%APPDATA%\brandx\`), creating the directory if needed.
- R5. The starter config is the full palette with every key present and commented with its default value, that is, the application-defaults layer serialised to YAML.
- R6. `brandx init` does not overwrite an existing config; it refuses or prompts.
- R7. The starter config and the config-reference docs derive from the single application-defaults source, so neither can drift from the code.

**Documentation**

- R8. A README covers installation, a quickstart (`init`, render a document, render an email), and points at the commented config as the field reference.
- R9. A worked example (sample markdown plus the commands to render it) ships in the repo.

**Licensing and updates**

- R10. The repo carries an MIT licence.
- R11. The documented update path is reinstalling the latest main via `uv` (`uv tool install --upgrade git+<repo>`), until PyPI versioned releases exist.

## Acceptance Examples

- AE1. Covers R1, R2. Given a machine with `uv` and the repo URL, a single `uv tool install` yields a working `brandx` command on PATH.
- AE2. Covers R4, R5, R6. Given no existing config, `brandx init` writes a fully-commented full-palette config; run a second time, it refuses to overwrite.
- AE3. Covers R7. Given a change to an application default value, the regenerated `init` template and config reference reflect it without hand edits.

## Scope Boundaries

**Deferred for later**

- PyPI publishing and the `uv tool install brandx` / `uvx` commands.
- Versioned releases, a changelog, and a release pipeline (deferred with PyPI).

**Owned by another track**

- Rendering behaviour and surfaces. Generic engine track.
- The config schema, the cascade, and the resolver. Identity config track.

**Outside this track's identity**

- Auto-scaffolding a config as a side effect of rendering. Rejected in favour of explicit `init`.

## Dependencies and Assumptions

- The `init` template and config reference depend on the application-defaults layer defined by the Identity config track as their single source.
- Assumes the public repo is hosted where `uv` can install from it (for example GitHub).
- Assumes the primary user has `uv` installed; bootstrapping `uv` itself is out of scope and covered by a docs pointer at most.

## Outstanding Questions

**Deferred to planning**

- The minimum Python version and how `uv` pins it.
- The mechanism by which the `init` template and config-reference docs are generated from the defaults source.
- The repo host and the exact install URL.
