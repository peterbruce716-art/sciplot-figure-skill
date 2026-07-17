# SciPlot Figure Skill

A reproducible scientific figure generation and validation framework for AI-assisted research workflows.

## Overview

SciPlot Figure Skill uses a VisualSpec JSON description to generate deterministic scientific figures and package the result as a portable, verifiable bundle.

Core capabilities:

- advisor-first data profiling, chart selection, plotting-policy checks, journal-style and CJK font records, and an offline AI visual-review contract

- VisualSpec-based figure descriptions
- deterministic Matplotlib rendering
- PNG, SVG, and PDF export
- semantic figure auditing
- SVG/PDF vector validation
- fixed-canvas edge safety validation for labels, legends, and callouts
- fixed-canvas plot-region and visible axis-spine validation for edges, coverage, and origin placement
- boxed-text glyph and padding validation for legend rows and callouts
- immutable shared sources for split curves and curve-derived fills
- native PDF figure clipping with target-region path or image hashing
- portable reproduction bundles
- checksums, environment records, and offline verification

## Validation Levels

The workflow reports different statuses depending on the evidence available:

- `semantic_strict_pass`: a reference image was supplied and visual, semantic, panel, and vector checks passed.
- `semantic_validated_pass`: no reference image was supplied, but a raw-data figure passed semantic and vector validation. This is a successful generated-figure workflow, not a visual-fidelity claim.
- `semantic_near_pass`: comparison evidence exists but does not meet the strict threshold.
- `render_only`: rendering completed, but the evidence needed for semantic validation was not available.

## Installation

Python 3.14 is required. Do not run this skill with Python 3.10, 3.11, 3.12, or 3.13; the validation and bundle gates are maintained against Python 3.14 only.

```bash
# Windows
py -3.14 -m venv .venv

# macOS/Linux
python3.14 -m venv .venv

# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python --version  # must report Python 3.14.x
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Quick Start: Generate From Data Without a Reference Image

### Advisor-first data workflow

```bash
py -3.14 scripts/scientific_figure_pipeline.py \
  --data examples/data/trend_comparison.csv \
  --intent examples/intents/trend_comparison.json \
  --x temperature --y response \
  --style generic_sci \
  --output-dir out/advisor --dry-run
```

The pipeline writes `advisor/`, `style/`, and optional `qa/` artifacts. These are advisory and traceable; deterministic VisualSpec, semantic, vector, and bundle checks remain the final gates.

This path renders the example, audits its semantics, validates SVG/PDF structure, writes checksums, and creates a portable verification bundle.

```bash
python scripts/run_reproduction.py \
  --spec examples/line_plot/visualspec_v2.json \
  --out-dir out/line_plot

python out/line_plot/verify.py
```

Expected final manifest status:

```text
semantic_validated_pass
```

## Strict Reference-Image Reproduction

Use this path when a source or reference image is available and visual fidelity must be measured.

```bash
python scripts/run_reproduction.py \
  --spec examples/line_plot/visualspec_v2.json \
  --source path/to/reference.png \
  --out-dir out/line_plot_strict \
  --qa-profile semantic \
  --require-strict

python out/line_plot_strict/verify.py
```

`--require-strict` requires `--source`; the command fails early when no reference image is supplied.

## Supported Plot and Annotation Types

The generic renderer currently supports:

- plots: line, scatter, errorbar, fill_between, grouped bar, stacked bar, heatmap, and contour
- annotations: text, arrow, rectangle, and polygon

Project-specific renderers can be supplied with `--script`, but custom command renderers cannot self-certify a semantic strict pass.

## Shared Geometry and PDF Trace

Use `scripts/shared_geometry.py` when one logical curve is drawn in segments or reused as a fill boundary. Every artist derived from that curve retains one source ID and geometry hash; conflicting hashes are a QA failure.

For multi-figure benchmarks, use `scripts/score_batch.py` with a `scientificfigure.visual_batch.v1` manifest. The batch command preserves source canvas size, writes per-figure comparison evidence, and fails when any required figure is missing or outside its predeclared visual thresholds.

Use `scripts/pdf_vector_trace.py` for exact visual reproduction from a PDF figure region. The tool preserves native clipping and transformations, exports PNG/SVG/PDF, and compares a fresh rasterization of the exported PDF with the source-page clip without resizing either image. It reports whether the visible source is made of PDF compound paths or an embedded raster image. This workflow is always `visual_trace_pass`, never semantic recovery of primary data.

## Bundle Contents

A completed output directory includes:

- `visualspec.json` and copied input data
- `render.py`, `reproduce.py`, and `verify.py`
- `outputs/render.png`, `outputs/render.svg`, and `outputs/render.pdf`
- semantic, vector, portability, and checksum reports
- optional `qa/canvas_safety.json` when `qa_policy.canvas_safety.enabled` is true
- optional `qa/plot_geometry_safety.json` when `qa_policy.plot_geometry_safety.enabled` is true
- optional `qa/boxed_text_safety.json` when `qa_policy.boxed_text_safety.enabled` is true
- environment metadata and a bundle lock
- `reproduction_manifest.json` and `run_report.json`

## Tests

Run tests from an activated Python 3.14 environment only:

```bash
python --version  # must report Python 3.14.x
python -m unittest discover -s scripts/tests -p "test_fast_*.py"
python -m unittest discover -s scripts/tests -p "test_score_batch.py"
python -m unittest discover -s scripts/tests -p "test_integration_*.py"
python scripts/release_acceptance.py
```

GitHub Actions is pinned to Python 3.14 and runs the fast suite, integration suite, source-free bundle test, and official release acceptance path.

## Repository Structure

```text
sciplot-figure-skill/
├── .github/workflows/
├── agents/
├── examples/
├── policies/
├── references/
├── schemas/
├── scripts/
│   └── tests/
├── styles/
├── CHANGELOG.md
├── SKILL.md
├── VERSION
└── requirements.txt
```

## Version

Current version: **v2.7.1**

## Scope and Limitations

The strict example verifies deterministic reproduction and the integrity of the validation chain. It does not by itself prove high-fidelity reconstruction of arbitrary paper screenshots. Real-paper benchmarks should be used to evaluate that separate capability.

## License

MIT License
