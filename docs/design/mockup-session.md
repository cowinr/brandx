# Interactive session — UX mockups

Text mockups of the brandx interactive session: the status panel in several states, the command vocabulary, a sample transcript, and the error/empty-state messages. This is the artifact reviewed and signed off (R11) before the loop is built (U4). Approval may revise panel layout, command names, or argument shapes; those feed U2 (panel renderer) and U4 (loop).

The panel is line-driven and reprinted after every command (R4). It shows resolved values (R4, "what you see is what renders"): the brand line shows the active config source and the resolved name; `set` overrides are listed so their effect is visible.

## Status panel — states

### Unfocused (just launched as bare `brandx`, no config file present)

```text
brandx · interactive session
──────────────────────────────────────────────────────
  file     (none — use: focus <file.md>)
  output   document
  brand    defaults              (no config file found)
  mark     monogram
  dest     preview
  set      (none)
──────────────────────────────────────────────────────
  focus  output  brand  mark  dest  set  unset
  render  reset  status  help  quit
brandx>
```

### Focused on a file, document output, defaults

```text
brandx · interactive session
──────────────────────────────────────────────────────
  file     note.md
  output   document
  brand    brand.yaml            ~/.config/brandx/brand.yaml
  mark     monogram              Richard Cowin
  dest     preview
  set      (none)
──────────────────────────────────────────────────────
  focus  output  brand  mark  dest  set  unset
  render  reset  status  help  quit
brandx>
```

### Email output, clipboard destination, one override

```text
brandx · interactive session
──────────────────────────────────────────────────────
  file     note.md
  output   email
  brand    brand.yaml            ~/.config/brandx/brand.yaml
  mark     monogram              Richard Cowin
  dest     clipboard
  set      colours.accent = #e63946
──────────────────────────────────────────────────────
  focus  output  brand  mark  dest  set  unset
  render  reset  status  help  quit
brandx>
```

### File destination

```text
  dest     file                  out.html
```

## Commands

| Command | Argument | Effect |
|---|---|---|
| `focus` | `<file.md>` | Focus a markdown file (replaces the current one). |
| `output` | `document` \| `email` | Choose the output form. |
| `brand` | `<path>` \| `default` | Use an alternate brand config; `default` returns to the home/auto config. |
| `mark` | `monogram` \| `avatar` | Choose the identity mark style. |
| `dest` | `preview` \| `clipboard` \| `file <path>` | Set the render destination. `file` needs a path. |
| `set` | `<key=value>` | Add a config override, dotted key (e.g. `set colours.accent=#e63946`). |
| `unset` | `<key>` | Remove one override. |
| `reset` | `[option]` \| `all` | Reset one option, or everything, to defaults. |
| `render` | — | Render the focused file to the current destination. |
| `status` | — | Reprint the panel. |
| `help` | `[command]` | List commands, or show help and choices for one. |
| `quit` | — | Exit the session (Ctrl-D also exits). |

Discovery (R5): the command footer is always on the panel; `help <command>` prints the argument choices for a single command.

## Sample transcript

```text
$ brandx note.md
brandx · interactive session
──────────────────────────────────────────────────────
  file     note.md
  output   document
  brand    brand.yaml            ~/.config/brandx/brand.yaml
  mark     monogram              Richard Cowin
  dest     preview
  set      (none)
──────────────────────────────────────────────────────
  focus  output  brand  mark  dest  set  unset
  render  reset  status  help  quit
brandx> render
Preview: /tmp/brandx-x8k2.html
... (panel reprints)
brandx> set colours.accent=#e63946
... (panel reprints, set line now shows the override)
brandx> render
Preview: /tmp/brandx-q4m1.html
brandx> output email
brandx> dest clipboard
... (panel reprints: output email, dest clipboard)
brandx> render
Copied rich text to the clipboard.
brandx> reset all
... (panel reprints: back to document, preview, no overrides)
brandx> quit
$
```

## Empty-state and error messages

```text
brandx> render
No file focused. Use: focus <file.md>

brandx> focus missing.md
File not found: missing.md  (focus unchanged)

brandx> dest file
dest file needs a path. Use: dest file <path>

brandx> brand /bad/path.yaml
Brand config not found: /bad/path.yaml  (brand unchanged)

brandx> render            # email output, on a non-macOS machine, dest clipboard
Clipboard is macOS-only. Set a different destination (dest preview | file <path>).
```

Notes carried into U2/U4:

- A bad `focus`, `brand`, or `dest` argument leaves the prior value unchanged and the session continues (no exit).
- `brand` validates the path when set, so a re-resolve never crashes the loop on a missing/malformed config.
- The brand line shows the config source label on the left and the resolved name on the right; when no file is focused the name column is blank (no frontmatter to resolve).
