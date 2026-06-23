---
date: 2026-06-23
topic: interactive-render-session
---

# Interactive render session

## Summary

Add a persistent interactive brandx session: focus a markdown file once, then set and re-set render options (document vs email, brand, mark, destination) with the current resolved settings always shown on screen, re-rendering in place each time. It stays stdlib and line-driven for now, structured so a full arrow-key TUI can replace the loop later.

## Problem Frame

`brandx render` today is a stateless one-shot. Every render is a full command line, and nothing shows you the current settings or which options exist, so each invocation is recalled from memory. A single document often needs several passes (preview as a document, then re-render as email to the clipboard, maybe with a `--set` colour override), and the friction is not the typing but the recall: there is no visible state to tweak from and no in-place discovery of what can be changed.

## Key Decisions

- **Visible status panel over a bare prompt.** The friction is recall, not typing. The session's core is an always-on display of the current settings, not just a command line that happens to loop.

- **Stdlib line-driven now, full TUI later.** A line-driven session with a reprinted status panel delivers the visible-state win without a new dependency. The option model is kept clean so a full arrow-key TUI can drop in later.

- **Bare `brandx` launches the session.** Running brandx with no subcommand drops into the interactive session, optionally focused on a file argument, making it the default face of the tool. This replaces today's print-help-on-no-args behaviour. `render` and `init` stay explicit subcommands, and the one-shot `brandx render` (including its pipeable stdout path) stays the scripting interface rather than being converted.

- **Panel shows resolved config.** The settings shown are the post-cascade resolved values (home config plus frontmatter plus in-session overrides plus brand), so what you see is what the next render produces.

## Requirements

**Session lifecycle**

- R1. Running `brandx` with no subcommand starts a persistent session that runs until the user explicitly exits; `brandx <file.md>` starts it focused on that file. `init` and `render` remain explicit subcommands.
- R2. The session can focus a markdown file at start and re-focus a different file mid-session without restarting.
- R3. `brandx render` remains a pure one-shot command, unchanged, including its pipeable stdout path.

**Visible state and discovery**

- R4. After every command the session reprints a status panel showing the current resolved settings: focused file, document vs email, brand, mark, and destination.
- R5. The options that can be changed are discoverable from within the session, so the user never recalls flags from memory.

**Options and rendering**

- R6. The user can set and re-set each option (document/email, brand, mark, destination, and individual config overrides) within the session, with each change reflected in the panel.
- R7. Settings are sticky across renders within a session; an explicit reset returns an option, or all options, to its default.
- R8. Rendering re-reads and re-parses the focused file each time, so edits made in an external editor are picked up on the next render without restarting.
- R9. In-session destinations are preview, clipboard, and file; stdout is not a session destination.

**Forward compatibility**

- R10. The session is structured so a full arrow-key TUI panel can replace the line-driven loop later without changing the option model or render behaviour.

## Key Flows

- F1. Tweak-and-render loop
  - **Trigger:** User starts a session focused on a markdown file.
  - **Steps:** Panel shows resolved settings; user changes an option; panel updates; user renders to the chosen destination; loop continues.
  - **Outcome:** Several renders of one document from a single session, each tweaked from visible state.
  - **Covers R1, R4, R6, R7.**

- F2. Edit-and-re-render
  - **Trigger:** User edits the focused `.md` in an external editor mid-session.
  - **Steps:** User re-renders; the session re-parses the file and produces output reflecting the edit.
  - **Outcome:** A manual edit-render loop without leaving the session or restarting.
  - **Covers R8.**

- F3. Switch output target
  - **Trigger:** User has previewed the document form and now wants the email form on the clipboard.
  - **Steps:** User switches document to email and destination to clipboard; panel reflects both; user renders.
  - **Outcome:** Two output forms of one document from one session.
  - **Covers R6, R9.**

## Acceptance Examples

- AE1. Resolved panel reflects an override
  - **Covers R4, R6.**
  - **Given** a session focused on a file with the default accent colour,
  - **When** the user sets a config override for the accent colour,
  - **Then** the status panel shows the new accent value, not the default.

- AE2. External edit picked up
  - **Covers R8.**
  - **Given** a session that has already rendered a focused file,
  - **When** the file is changed in an external editor and the user renders again,
  - **Then** the new output reflects the edited content.

- AE3. Reset returns to default
  - **Covers R7.**
  - **Given** a session with a brand override applied,
  - **When** the user resets that option,
  - **Then** the panel shows the configured default brand and the next render uses it.

## Scope Boundaries

**Deferred for later**

- PDF and image export — a separate track, noted here but not designed in this brainstorm.
- The full arrow-key TUI panel — the line-driven session is structured to accept it later, but it is not built now.
- File-watching or automatic re-render on change — the loop stays manual; R8 covers picking up edits on the next explicit render.

**Outside this product's identity**

- Markdown authoring or editing inside the session. brandx applies branding; producing or editing the markdown stays with whatever wrote it.

## Outstanding Questions

**Deferred to planning**

- Whether any session settings persist across separate sessions. Default assumption: no — each session starts from the configured defaults, and persistence is not in scope unless a reason surfaces during planning.
