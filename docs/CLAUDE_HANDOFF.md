# Claude Handoff — QA Raman Manuscript, Builds, and Backlog

This document captures the essential state of the project so another agent can continue seamlessly. It summarizes deliverables, file paths, compile commands, and the remaining backlog of experiments.

## Deliverables (ready to submit)

- Overleaf bundle: `qa_raman_overleaf.zip`
- Nature Communications submission: `submission/naturecomms_submission.zip`
- arXiv upload bundle: `arxiv_package.zip`

## Manuscript state

- Main paper: `manuscript.tex` → compiled `manuscript.pdf`
- Supplementary Info: `SI.tex` → compiled `SI.pdf`
- Bibliography: `references.bib`
- TikZ Figure 0 is embedded natively in `manuscript.tex` with label `fig:qa_geometry_overview`.
- “How to read Figure 0” paragraph added in Background.
- “Limitations” paragraph added in Conclusion.
- The k-NN sweep figure is commented out to avoid missing-graphic warnings (image not included yet).

### Figure paths in manuscript

- QA geometry (Figure 0): native TikZ (no external file needed in the main manuscript build).
- Benchmark composite: `artifacts/qa_benchmark_report.png`
- Residue histograms: `artifacts/cm24_hist.png`, `artifacts/fm24_hist.png`

## Submission packages

### Nature Communications — `submission/`

- `manuscript_final.{tex,pdf}`
- `SI_final.{tex,pdf}`
- `references.bib`
- `cover_letter_naturecomms.txt`
- `figures/`: `figure0_qageometry.{tex,pdf}`, `qa_benchmark_report.png`, `cm24_hist.png`, `fm24_hist.png`
- `artifacts/`: `qa_ablation_table.csv`, `qa_ablation_table.md`, `qa_raman_features.csv`, `qa_raman_mapping.json`
- `README_submission.txt`
- Zipped: `submission/naturecomms_submission.zip`

### arXiv — `arxiv/`

- `manuscript_arxiv.tex` (Figure 0 via PDF include, no TikZ requirement)
- `manuscript_arxiv.bbl` (TeX uses `\input{...}`; no BibTeX needed)
- `SI_arxiv.tex`
- `figures/`: `figure0_qageometry.pdf`, `qa_benchmark_report.png`, `cm24_hist.png`, `fm24_hist.png`, `graphical_abstract.pdf`
- `README_arxiv.txt`
- Zipped: `arxiv_package.zip`

## Build commands (local)

- Manuscript
  - `pdflatex -interaction=nonstopmode manuscript.tex`
  - `bibtex manuscript`
  - `pdflatex -interaction=nonstopmode manuscript.tex`
  - `pdflatex -interaction=nonstopmode manuscript.tex`

- SI
  - `pdflatex -interaction=nonstopmode SI.tex`
  - `bibtex SI`
  - `pdflatex -interaction=nonstopmode SI.tex`
  - `pdflatex -interaction=nonstopmode SI.tex`

## Cover letter

- Path: `submission/cover_letter_naturecomms.txt`
- Tone: interpretability, novelty (QA invariants + residues), reproducibility; no overclaims.

## Outstanding experiments (not blocking submission)

Quick wins (1 day)
- Regenerate k-NN sweep figure: `scripts/qa_knn_sweep.py` → produce `artifacts/qa_knn_sweep.png` and re-enable figure block.
- Noise robustness (±5–10%): inject Gaussian noise, re-evaluate LOO; report Δacc.
- Subsample stability: 10× 80/20 splits; mean±std accuracy.
- k-fold CV: stratified k=5 to complement LOO.
- Per-class residue histograms: extend `scripts/qa_residue_histograms.py` with label filtering.

Method variations (2–3 days)
- Peak-finding robustness: add Savitzky–Golay smoothing + prominence/SNR thresholds to `scripts/qa_raman_map_files.py`; sweep parameters.
- Feature ablations (expanded): vary top-N peaks (3/5/7), add/remove ratio families, z-score vs rank scaling.
- Classifier baselines: SVM (RBF) and RandomForest on QA feature set; compare to weighted kNN.
- Distance weighting sweep: inverse vs inverse-squared vs softmax temperature.
- Calibration sensitivity: vary diamond anchor `s` ±2%/±5% and report impact.

Generalization & error analysis (3–5 days)
- Leave-instrument-out (if metadata available), misclassification overlays, residue-basin conditioned accuracy, bootstrap CIs.

QA-specific physics extensions (5–10 days)
- Δe sidebands (Stokes/Anti-Stokes) as features; `mod-24` torus indices; DFT/phonon desk correlations.

## Known minor items

- `scripts/fetch_rruff_materials.py`: confirm both guards use `args.max_per_class`.
- JCAMP-DX parser (`qa_io/jcamp_dx.py`): harden for odd encodings; test non-monotonic x / <3 peaks.
- Ensure `--modality Raman` is passed consistently in exporters to avoid IR/XRD contamination.

## Graphical abstract

- Source: `figures/graphical_abstract.tex`
- PDF: `figures/graphical_abstract.pdf`
- For portals requiring PNG (e.g., 1200×675), rasterize from the PDF (ImageMagick or similar).

## TL;DR

- All three packages (Overleaf, Nature Comms, arXiv) are created and validated.
- Manuscript is clean, labels resolve, SI compiles standalone, cover letter included.
- Quick-win experiments and robustness runs can further strengthen a revision but are not required for initial submission.

