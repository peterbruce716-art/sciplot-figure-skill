# Statistical Reporting Protocol

StatisticsReport records what is known about panel-level statistics without allowing the plotting workflow to invent significance.

## Status semantics

- declared: provided by the user, source metadata, or an auditable upstream analysis.
- unknown: not available. Reproduction may still pass, but publication readiness is conditional or blocked.
- not_applicable: appropriate for qualitative, schematic, native image, or annotation-only panels.

## Required boundaries

- Do not auto-select a hypothesis test and mark it declared.
- Do not add significance stars, p-values, or multiple-comparison labels unless they are declared and traceable.
- Record n_definition, center, spread, test status, source files, columns, filters, aggregation, sample definition, random seed, split, metric definition, and data hash when available.
- Import declared statistics with scripts/build_statistics_report.py --statistics-json <json-or-path> when a user or auditable upstream analysis supplies panel-level statistics. Treat those values as declarations, not recomputed results, and keep their source trace.
- Treat weak, negative, or non-significant results as drawable. Use advisory warnings to prevent over-interpretation.
- Block publication_ready when a quantitative panel has unknown n definition, center/spread, test status, or source trace required for the claim.

## Manifest role

When available, add statistics_report and publication_readiness to the final manifest. These fields describe manuscript-readiness evidence and do not upgrade visual, semantic, vector, or bundle QA status.
