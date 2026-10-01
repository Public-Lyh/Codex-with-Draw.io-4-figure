---
name: drawio-paper-figures
description: Create and revise editable paper architecture diagrams, method illustrations, and conceptual figures using draw.io XML and command-line exports to PNG, SVG, and PDF. Use when the user requests a draw.io figure or an editable research diagram.
---

# Editable paper figures

Turn the user's research content into an editable diagram and inspect the exported result. Use the locally installed `drawio-render` workflow. Read [local-installation.md](references/local-installation.md) for its exact executable command; the installer fills this reference with machine-specific paths.

## Design from evidence

- Read the relevant manuscript, method description, or source figure. Identify the figure's message, real modules, data flow, and any equations or measured values that must be preserved. Do not invent experimental results, dependencies, or novelty claims.
- Match the requested figure type and publication dimensions. When dimensions are unspecified, choose a readable layout and state the assumption. Ask only about missing information that materially changes the content.
- Use a short design outline when a complex figure benefits from one, then create the figure within the user's authorized scope. Do not impose a separate approval gate for routine drawing and revision.

## Produce editable XML

Save one figure per `.drawio` file under `diagrams/in/`, and exports under `diagrams/out/`, unless the user specifies other paths. Use an uncompressed `mxfile` containing one `diagram/mxGraphModel`, or a bare `mxGraphModel`.

Use unique cell IDs, `parent="1"` for top-level cells, explicit geometry, and edges with correct source and target IDs. Prefer attached, orthogonal connectors over loose line segments. Keep text editable. Use `html=0` on labels and nodes and omit `whiteSpace=wrap`: draw.io HTML labels produce SVG `foreignObject` elements that external PDF converters may omit. Automatic wrapping can also force HTML output even with `html=0`. For native labels, escape XML attributes and use `&#xa;` for line breaks. Avoid unsupported HTML/MathJax labels in this workflow; use plain Unicode math or individually positioned native text when appropriate.

Read [layout.md](references/layout.md) for sizing, grouping, and XML conventions. Prefer a small, consistent palette, aligned boxes, legible font sizes, and clear arrow direction. Do not assume `--layout` or Mermaid import exists in the installed draw.io version. Explicit XML coordinates are the portable default.

## Render and inspect

**You may skip the image check if the user requests it.**

Run the command in the local installation reference, or these commands when it is available on PATH:

```bash
drawio-render diagrams/in/figure.drawio diagrams/out/figure.png png 2
drawio-render diagrams/in/figure.drawio diagrams/out/figure.svg svg 1
drawio-render diagrams/in/figure.drawio diagrams/out/figure.pdf pdf 1
```

The wrapper runs draw.io CLI, using a virtual X display on Linux; no browser or real desktop interaction is needed. PDF must use `.drawio → SVG → Inkscape` (default) or CairoSVG, through the same wrapper. Do not bypass it with draw.io's direct PDF export.

Check exit status and actual output files. A nonempty file alone does not establish visual correctness. Inspect a PNG preview for clipped labels, overlap, tiny text, missing arrows, contrast, and margins. For large images, create a preview of at most 1600 pixels on the long edge before using an image-viewing tool; retain the full-resolution output. Also inspect the PDF when it is a requested deliverable, because font substitution can differ. Revise XML and re-export when a defect is visible.

If rendering fails, read the corresponding `<output>.<ext>.log`, run `drawio-render doctor --pdf-engine inkscape`, and address the specific failure. Do not change system-wide security settings or resource limits as a generic fix. Use `--no-sandbox` only when the local environment requires it and explain that choice. Stop repeating an unchanged failing command.

## Deliver

Return absolute links to the editable `.drawio` and requested exports. Briefly explain substantive design choices, any assumptions, and whether visual inspection was possible. Preserve the editable source and earlier user work during revisions. If a requested output could not be validated, identify that output rather than calling the whole workflow verified.
