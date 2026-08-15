# brandx

Generic, identity-free tool that renders markdown into a branded HTML document or an Outlook-safe email, driven by a user-owned YAML brand config. The engine holds zero person-specific knowledge: identity is pure data, the engine is generic.

## Commands

```bash
uv sync                             # install runtime deps plus the dev group
uv run pytest                       # run the test suite
uv run pytest tests/test_email_render.py   # single test file
uv run ruff check                   # lint
uv run ruff format                  # format
uv run brandx render note.md -o out.html        # render a document
uv run brandx render --email note.md -o email.html   # render Outlook-safe email
uv run brandx render --email note.md --clipboard     # copy rich text (macOS)
uv run brandx init                  # scaffold a starter brand config
```

Install for use: `uv tool install git+https://github.com/cowinr/brandx`.

## Layout

- `src/brandx/config/` — the four-layer config cascade: `defaults` → home YAML → document frontmatter → invocation flags, resolved by `resolver.py` against `schema.py`, located by `discovery.py`. Always yields a complete config.
- `src/brandx/render/` — one `pipeline` produces semantic HTML, then two renderers style it: `document.py` (CSS-var `<style>` block, codehilite) and `email.py` (Outlook-safe). Plus `assets.py` (base64 embedding), `callouts.py`, `tasklists.py`.
- `src/brandx/cli.py` — entry point (`brandx` console script); `session.py`/`tui.py` drive the interactive render session; `initcmd.py`, `output.py`, `clipboard.py`, `docsgen.py`.
- `tests/` — pytest, one file per module.
- `docs/` — `plans/` and `brainstorms/` (the build history and rationale), `design/` (signed-off HTML mockups the renderers build against), `config-reference.md`.

## Conventions a linter cannot enforce

- **Two renderers, one structural pass.** The shared pass emits semantic HTML only; each renderer styles independently. Keep them separate.
- **The email renderer is Outlook-safe by construction:** 100% inline styles, presentation-table layout, no `<style>` block, plain monospace code. Never enable codehilite or emit class-based syntax spans on the email path — Outlook and Gmail strip them.
- **Identity is data, never code.** No person-specific values in the engine; everything visual comes from the resolved config.
- **Reproduce ea-brand technique, not code.** `~/projects/ea-brand` is the pattern source for the hard parts (Outlook primitives, base64 embedding, dependency-free highlighting); reproduce the technique, do not fork.
- **Outlook fidelity cannot be tested in automation.** The email golden-HTML snapshot guards structural drift only; true fidelity needs a manual paste-into-Outlook check when the email surface changes.
- **The letterhead banner is opt-in** (`identity.letterhead`, default false). Its absence from a default render is the design, not a bug. Tests that need it turn it on through `_letterhead_cfg()`.
- **A `--set` value is always a string.** Any typed config key must be coerced at resolution time, in `ResolvedConfig.__init__`, via `resolver._as_bool` or `resolver._as_number`. Skip it and `--set key=false` reads as truthy, while a numeric key raises `TypeError` deep inside a renderer. Coerce in the resolver, never at the read site: there are two renderers and they would drift.
- `ResolvedConfig` is immutable. Do not mutate it after resolution.
- **Ruff is pinned to one minor** in the `dev` dependency group. 0.16 widened the default rule set, which turned a clean repo into 47 findings with no code change. Widen the pin only alongside a pass that clears whatever the new version reports.

## Boundaries

- Do not weld identity or assets into the engine.
- Do not add syntax highlighting to the email renderer.
- Do not fork ea-brand source.
