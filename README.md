# SciPlot Figure Skill

A reproducible scientific figure generation and validation framework for AI-assisted research workflows.

## Overview

SciPlot Figure Skill provides a structured workflow for creating scientific figures with reproducibility, semantic validation, and vector-output verification.

Core ideas:

- VisualSpec-based figure description
- deterministic rendering
- semantic figure auditing
- SVG/PDF vector validation
- reproduction bundles
- portable verification workflow

## Supported Outputs

- PNG
- SVG
- PDF

## Features

### Figure Specification

Figures are described using VisualSpec JSON rather than scattered plotting scripts.

### Validation

The framework can validate:

- rendered image existence
- semantic consistency
- vector output integrity
- bundle reproducibility
- environment information

### Reproduction Bundle

Generated packages contain the information required to reproduce and verify a figure on another machine.

## Validation Status

Version: v2.5

Tested workflow:

- strict line plot reproduction
- semantic audit
- SVG vector validation
- PDF export validation
- reproduction bundle verification

Example status:

```
semantic_strict_pass
vector_validation_pass
verify.py pass
```

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

Example:

```bash
python scripts/run_reproduction.py examples/line_plot/visualspec_v2.json
```

## Repository Structure

```
sciplot-figure-skill/
├── examples/
├── references/
├── schemas/
├── scripts/
├── tests/
├── requirements.txt
└── CHANGELOG.md
```

## Design Philosophy

This project focuses on reproducible scientific graphics rather than simple plotting.

The goal is:

```
Figure specification
        ↓
Deterministic rendering
        ↓
Semantic validation
        ↓
Vector verification
        ↓
Reproducible scientific artifact
```

## Roadmap

### v2.5

- VisualSpec v2
- semantic QA
- deterministic bundle workflow
- vector validation

### Future

- more plot adapters
- improved source-image reconstruction
- larger scientific figure benchmarks

## License

MIT License
