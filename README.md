# brandx

**brandx** renders markdown into a branded document or an Outlook-safe email, driven by a user-owned YAML brand config. The engine holds zero person-specific knowledge: identity is pure data, the engine is generic.

## Usage examples

```bash
# Convert to HTML file
brandx render note.md -o note.html

# Just preview the HTML (opens a browser)
brandx render note.md --preview

# Convert to Outlook-safe HTML (ready for paste)
brandx render --email note.md --clipboard

# Change a config
brandx render note.md --set colours.accent=#e63946

# Use the hansard branding
brandx render note.md --brand ~/.config/brandx/hansard.yaml --preview
```

## Install

Requires Python 3.11 or later and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/cowinr/brandx
```

This places a `brandx` command on PATH on macOS, Windows, and Linux.

To install from a local checkout instead:

```bash
git clone https://github.com/cowinr/brandx
cd brandx
uv tool install .
```

## Quickstart

**1. Scaffold your brand config**

```bash
brandx init
```

This writes a fully-commented starter config to `~/.config/brandx/brand.yaml` (Windows: `%APPDATA%\brandx\brand.yaml`), creating the directory if needed. Every key is present with its default value and a comment explaining what it does.

Run again without `--force` and it refuses to overwrite, so you can always regenerate the template safely:

```bash
brandx init --force   # overwrites an existing config
```

**2. Edit your brand**

Open `~/.config/brandx/brand.yaml` and fill in your details:

```yaml
identity:
  name: Alex Renwick     # your full name
  role: Senior Analyst   # shown in the letterhead beneath your name

colours:
  primary: '#1c2b39'     # primary heading colour
  accent: '#0d8a7d'      # accent bars and active elements
```

Every key has a default, so you only need to set what you want to change.

**3. Render a document**

```bash
brandx render examples/sample-note.md -o note.html
```

Add `--preview` to open the result in a browser instead of (or alongside) writing a file:

```bash
brandx render examples/sample-note.md --preview
```

**4. Render an Outlook-safe email**

```bash
brandx render --email examples/sample-note.md -o email.html
```

On macOS, `--clipboard` copies rich text directly to the clipboard, ready to paste into Outlook or Mail:

```bash
brandx render --email examples/sample-note.md --clipboard
```

On Windows and Linux the clipboard backend is not yet available; a clear message is printed instead and `-o FILE` works on all platforms.

**5. Override a config value for one render**

Use `--set KEY=VALUE` with dotted notation. The flag sits at the top of the cascade and overrides everything else without touching the config file:

```bash
brandx render examples/sample-note.md --set colours.accent=#e63946
```

`--set` is repeatable.

## The cascade

brandx resolves brand values from four layers, lowest to highest:

1. **Application defaults** — a value for every key, so output is always sane with no config at all.
2. **Home config** (`~/.config/brandx/brand.yaml`) — your personal brand.
3. **Document frontmatter** — per-document overrides in the markdown YAML header.
4. **Invocation flags** (`--set KEY=VALUE`, `--mark`) — one-off overrides at render time.

The same key name at a higher layer wins. Nested blocks (such as `colours`) are deep-merged, so setting one colour key leaves the rest of the palette intact.

## Config reference

Full key listing with defaults and descriptions: [`docs/config-reference.md`](docs/config-reference.md).

The reference is generated from the single application-defaults source — run `brandx docsgen` to regenerate it after changing defaults. It cannot drift from the code.

## Output surfaces

**Document** — a branded HTML page with a web font (`<link>`), a `<style>` block with CSS variables built from your palette, syntax-highlighted fenced code blocks, a print stylesheet, and a letterhead with your mark (monogram or avatar).

**Email** — 100% inline styles, presentation-table layout, Outlook-safe callout bars, plain monospace code (no syntax highlighting; email clients strip class-based styles), web-safe font stack, and base64-embedded avatar. Prints a warning when total size approaches the Gmail clip threshold.

## Selecting the identity mark

The letterhead mark defaults to a two-letter monogram derived from your name. Pass `--mark avatar` (or set `identity.mark: avatar` in the config) to use an image instead:

```bash
brandx render examples/sample-note.md --mark avatar
```

Point `identity.avatar` in the config at your image path. A smaller crop for email is optional (`identity.avatar_email`); it falls back to the main avatar when absent.

## Alternate brand config

Use `--brand PATH` to render with a different config file without touching the home config. Useful for testing a brand or managing multiple identities:

```bash
brandx render report.md --brand ~/configs/client-brand.yaml
```

## Interactive session

Running `brandx` with no subcommand (optionally `brandx <file.md>`) drops into an interactive session. Instead of re-typing a full command for every render, you focus a file once, then set and re-set options against an always-visible status panel and re-render in place:

```text
$ brandx note.md
brandx · interactive session
──────────────────────────────────────────────────────
  file     note.md
  output   document
  brand    ~/.config/brandx/brand.yaml
  mark     monogram               Alex Renwick
  dest     preview
  set      (none)
──────────────────────────────────────────────────────
  focus  output  brand  mark  dest  set  unset
  render  reset  status  help  quit
brandx>
```

The panel reprints after every command and shows the resolved settings, so what you see is what the next `render` produces.

| Command | Argument | Effect |
|---|---|---|
| `focus` | `<file.md>` | Focus a markdown file (replaces the current one). |
| `output` | `document` \| `email` | Choose the output form. |
| `brand` | `<path>` \| `default` | Use an alternate brand config, or return to the default. |
| `mark` | `monogram` \| `avatar` | Choose the identity mark style. |
| `dest` | `preview` \| `clipboard` \| `file <path>` | Set the render destination. |
| `set` | `<key=value>` | Add a config override (e.g. `set colours.accent=#e63946`). |
| `unset` | `<key>` | Remove one override. |
| `reset` | `[option]` \| `all` | Reset one option, or everything, to defaults. |
| `render` | — | Render the focused file to the current destination. |
| `status` | — | Reprint the panel. |
| `help` | `[command]` | List commands, or show help for one. |
| `quit` | — | Exit (Ctrl-D also exits). |

Rendering re-reads the focused file each time, so you can edit it in your editor and `render` again without restarting. The one-shot `brandx render` is unchanged and stays the scriptable, pipeable path.

## Update

```bash
uv tool install --upgrade git+https://github.com/cowinr/brandx
```

## Licence

MIT. See [LICENSE](LICENSE).
