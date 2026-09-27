# Local installation

The installer replaces this file in the selected agent's skill directory with the absolute renderer command and chosen PDF backend.

For a manually copied skill, first run `drawio-render doctor --pdf-engine inkscape`. If that command is absent, use the platform installation guide in the Codex-with-Draw.io-4-figure checkout. Do not invent a machine-specific path.

From a checkout with dependencies already installed, the equivalent command is:

```bash
python3 scripts/drawio_render.py input.drawio output.svg svg 1
```

On Windows use `python` instead of `python3`. Paths containing spaces must be quoted according to the active shell. An absolute Python interpreter plus the absolute `scripts/drawio_render.py` path also works without PATH configuration.
