# Chart Selection

Chart decisions combine the declared figure intent with profile evidence. Typical mappings are:

| Intent | Starting point | Required disclosure |
| --- | --- | --- |
| Trend or temporal change | line, scatter, or uncertainty band | units, ordering, sampling, uncertainty |
| Group comparison | box/violin plus raw points | group counts and uncertainty semantics |
| Distribution comparison | box, violin, ECDF, or strip | sample size and preprocessing |
| Correlation | scatter plus explicitly named fit | fit model, units, and non-causal wording |
| Model vs experiment | observed/predicted overlay or parity plot | source encoding and error definition |
| Composition | sorted horizontal bars | denominator and category order |

The recommendation is not a replacement for domain judgment. Explicit user requests are preserved with a risk warning when a familiar chart can mislead.
