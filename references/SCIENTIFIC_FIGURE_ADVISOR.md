# Scientific Figure Advisor

SciPlot now has an optional Advisor Layer for data-driven redraws. It produces structured artifacts before rendering:

1. `data_profile.json`: deterministic column types, missingness, group counts, descriptive statistics, skewness, IQR outlier counts, and warnings.
2. `figure_intent.json`: the claim, task type, audience, uncertainty semantics, and priority variables.
3. `chart_decision.json`: a recommended chart, alternatives, rejected choices, reasons, required visual elements, and warnings.
4. `policy_report.json`: configurable scientific plotting policy findings.

The Advisor Layer is advisory. It does not modify input data, delete outliers, or bypass VisualSpec and deterministic QA. A warning is not a statistical conclusion; review the claim, sampling design, units, and uncertainty definition before accepting a chart.

## Recommended sequence

```powershell
py -3.14 scripts\profile_scientific_data.py --input data.csv --output outputs\data_profile.json --group treatment --x temperature --y stress
py -3.14 scripts\recommend_scientific_chart.py --profile outputs\data_profile.json --intent intent.json --output outputs\chart_decision.json --x temperature --y stress
py -3.14 scripts\evaluate_scientific_plot_policy.py --context context.json --output outputs\policy_report.json
```

Use `scientific_figure_pipeline.py` when these stages should be resumed from one output directory. Use `--dry-run` to stop before rendering. For raw-data plots, `--generate-visualspec` supports a simple line example; complex plot types should be authored explicitly in VisualSpec or a project renderer.

## Interpretation boundaries

- A continuous variable should not be treated as a categorical axis without a documented reason.
- Small groups should expose individual observations; do not infer that a mean-only bar is invalid in every context.
- An error bar has no meaning until SD, SEM, confidence interval, or another definition is recorded.
- Correlation and trend recommendations do not establish causation.
- The Advisor helps most with CSV/TSV/Excel data redraws. It is only auxiliary for screenshot fidelity, technical route maps, and mechanism schematics.
