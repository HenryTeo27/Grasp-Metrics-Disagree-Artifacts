# V4 Figure Contracts

The output surface is a static LaTeX/PDF paper, not an interactive dashboard.
All numerical charts derive from frozen evidence. Matplotlib is the renderer;
PDF is the publication format and PNG is the visual-QA format.

| Figure | Question / supported takeaway | Data and form | Encoding and QA |
| --- | --- | --- | --- |
| Contract examples | Can record-level contact and physical support look similar? | Three preselected registered controls 000/001/002, snapshot at 8 s; actual MuJoCo renderings plus computed contract labels | Object green, pads blue, environment gray. Label semantics in text, no color-only verdicts. About 170 mm wide. Check nonblank pixels, framing and label fit. Not a statistical sample. |
| Experimental contrasts | What variable changes in each comparison? | Three-row method diagram, no numerical estimand | Rectangles and arrows, explicit endpoints, no implied common success denominator. About 170 mm wide. |
| Risk, coverage and utility | Does geometry add value over the full-wrench baseline? | Five registered threshold points on 240 controls; K=1/3/6 on the same 120 decision scenes | B4 large open circles, B5 small open squares/dashed line so ties remain visible. Axes start at zero; risk ceiling shown. Unknowns stay in source tables. Two panels at about 170 mm total width. Exact counts in tables, not inferred from curves. |

Use a restrained gray/blue/teal/red palette and shapes/line styles as redundant
identifiers. Do not rescale axes to exaggerate a null or small difference.
Inspect figures alone and in the final page layout. If the operating points
coincide, retain and state the overlap rather than jittering scientific values.
