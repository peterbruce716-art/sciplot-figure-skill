# Workflow Profile Examples

From the skill root with Python 3.14:

```powershell
py -3.14 scripts\sciplot.py run --input examples\data\trend_comparison.csv --profile quick --out-dir out\preview
py -3.14 scripts\sciplot.py run --input examples\data\trend_comparison.csv --profile standard --out-dir out\manuscript
py -3.14 scripts\sciplot.py validate --project out\manuscript --profile standard
py -3.14 scripts\sciplot.py finalize --project out\manuscript --profile audit --bundle delivery\figure_bundle
```

Use `--claim reusable` only with a complete data-swap template plus baseline and changed input evidence. Use `trace-pdf` with a `scientificfigure.pdf-clip-manifest.v1` file for fresh, source-bound PDF tracing; PDF trace is never semantic data recovery.
