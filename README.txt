Overleaf Package: QA Raman Spectroscopy (Quantum Arithmetic)
===========================================================

Contents
--------
- manuscript.tex            (main paper)
- manuscript.pdf            (compiled PDF)
- SI.tex                    (supplementary information)
- SI.pdf                    (compiled SI)
- references.bib            (bibliography)
- figures/                  (TikZ source + compiled outputs)
- artifacts/                (benchmark images, histograms, CSVs)

Compile (manual)
----------------
If latexmk is not available, use the standard pdflatex/bibtex sequence:

1) Main manuscript
   pdflatex -interaction=nonstopmode manuscript.tex
   bibtex manuscript
   pdflatex -interaction=nonstopmode manuscript.tex
   pdflatex -interaction=nonstopmode manuscript.tex

2) Supplementary Information
   pdflatex -interaction=nonstopmode SI.tex
   bibtex SI
   pdflatex -interaction=nonstopmode SI.tex
   pdflatex -interaction=nonstopmode SI.tex

Notes
-----
- The manuscript embeds Figure 0 via native TikZ (no external PDF needed).
- The k-NN sweep figure is commented out until the image artifact is provided.
- All figures referenced in the paper are present under artifacts/ and figures/.
- The code-generated artifacts (CSV/PNG) can be refreshed using scripts/ in the repo root.

Overleaf Tips
-------------
- If Overleaf complains about missing packages, switch the compiler to pdfLaTeX.
- Ensure the project root includes this README, manuscript.tex, SI.tex, references.bib, and the artifacts/ and figures/ directories.
