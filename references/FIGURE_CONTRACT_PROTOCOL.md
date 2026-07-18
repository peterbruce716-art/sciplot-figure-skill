# Figure Contract Protocol

Use FigureContract to bind a scientific question to explicit evidence and panel roles before chart selection. It is a planning artifact, not a renderer input replacement.

## Required boundaries

- Keep core_claim as unknown unless the user or source evidence declares it.
- Record every inferred evidence item in assumptions or item-level provenance.
- Record VisualSpec layout inferences in layout.inference_log when hero_panel_id, narrative_order, archetype, or hero-panel weights are inferred, derived, or defaulted.
- Use approval.mode=auto for reproducible pipelines, interactive for major unresolved panel/story choices, and strict only when an approved contract already exists.
- Treat hero_panel_id as optional. Do not invent a hero panel for quantitative_grid or when no panel is scientifically dominant.
- Keep panel_plan evidence IDs referentially valid against evidence_chain IDs.
- Prefer journal names as style context only; never present local presets as official journal templates.

## Pipeline role

FigureContract feeds FigureIntent, ChartDecision, VisualSpec layout hints, StatisticsReport, reviewer advisory, and manifest provenance. It must not bypass deterministic rendering, semantic audit, vector checks, visual scoring, bundle locking, checksums, or portability validation.

## Failure policy

Fail closed for schema errors, duplicate panel IDs, broken evidence references, invalid hero panel references, multiple hero panels, or unapproved strict mode. Warn, but continue, for low information content, missing hero in an asymmetric draft, unknown statistics, weak effects, or negative results.
