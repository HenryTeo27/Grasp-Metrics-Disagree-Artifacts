# V4.5 LaTeX Source

This is a multi-file manuscript project. It requires an existing TeX
installation with IEEEtran and the standard packages named in the sources.
No simulator, network, or research dataset is required to build the PDFs.

Author main paper:

```text
pdflatex -interaction=nonstopmode -halt-on-error main.tex
bibtex main
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Repeat the same four commands with `supplement`, `main_review`, or
`supplement_review` in place of `main`. The review wrappers remove author
fields; normal prior-work citations remain. This is review preparation, not a
certification against an unconfirmed IROS 2027 anonymity policy.

The `.bbl` files and figures are supplied. The source ZIP is distinct from the
evidence ZIP and the optional core-raw companion. For arXiv or a publisher,
follow that service's source-upload and supplementary-file requirements;
do not upload the entire evidence archive as manuscript source.

V4.5 changes presentation only. Existing V3/V4 manuscripts and scientific
code, protocols, source records, labels, and frozen thresholds remain intact.
