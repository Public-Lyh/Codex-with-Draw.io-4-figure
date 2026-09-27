# Layout and XML conventions

Start from the bundled `examples/pipeline.drawio` when a simple left-to-right method diagram is appropriate. Do not copy its generic module names into an unrelated research method.

- Choose a canvas and hierarchy before positioning individual elements. Use one visual direction for the main flow; distinguish feedback or training-only connections with labels and line style.
- Keep related modules within a lightly shaded group. Allow space for edge labels. Consistent widths and 24–48 pixel gaps are useful starting values, not mandatory publication dimensions.
- Use a font installed in the rendering environment. Arial may be substituted on Linux; Liberation Sans or Noto Sans are alternatives. Test CJK text with an installed CJK font. Do not distribute proprietary fonts with the figure.
- Set `html=0` and an explicit font size on text-bearing cells. Omit `whiteSpace=wrap`: even with `html=0`, automatic wrapping can force HTML export. Use explicit line breaks (`&#xa;`) and sufficiently large geometry. Avoid decorative shadows and excessive gradients. Use plain native text for export reliability.
- An edge should usually have `edgeStyle=orthogonalEdgeStyle;endArrow=block;endFill=1;html=0;` and `<mxGeometry relative="1" as="geometry"/>`.
- Keep labels concise without changing their scientific meaning. Explain necessary abbreviations in the caption rather than filling boxes with paragraphs.

Minimal editable structure:

```xml
<mxfile><diagram name="Figure"><mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="module" value="Feature encoder" vertex="1" parent="1"
          style="rounded=1;html=0;fontSize=18;">
    <mxGeometry x="40" y="40" width="180" height="80" as="geometry"/>
  </mxCell>
</root></mxGraphModel></diagram></mxfile>
```

For publication, verify appearance at the actual print width. PNG scale increases raster resolution; it does not fix an unreadable design. SVG/PDF remain vector outputs, subject to the content and fonts used.
