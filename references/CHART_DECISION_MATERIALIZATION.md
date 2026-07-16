# Chart decision materialization

`ChartDecision` is an intermediate decision, not a render. `chart_decision_to_visualspec.py` maps supported chart types to explicit artists and records the decision hash, source columns, uncertainty source, and confirmation requirements. Unsupported mappings raise an error with the missing mapping instead of silently substituting another chart.
