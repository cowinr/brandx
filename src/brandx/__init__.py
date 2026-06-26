"""brandx — generic identity-free markdown-to-branded-document tool.

Driven by a user-owned YAML brand config resolved through a four-layer cascade:
application defaults < home YAML config < document frontmatter < invocation flags.

Install from a public Git repo:
    uv tool install git+<repo-url>

Usage:
    brandx init                        # write starter config to ~/.config/brandx/brand.yaml
    brandx render <file.md>            # render a document
    brandx render --email <file.md>    # render an Outlook-safe email
"""

__version__ = "1.0.1"
