# Render-derived policy context

`scripts/build_policy_context_from_render.py` converts the actual `VisualSpec` artist tree, resolved theme, optional semantic metadata, and deterministic QA reports into a small JSON context. Policy evaluation should consume this artifact after materialization/rendering, so checks can see dual y-axes, 3D projections, text density, font selection, and uncertainty semantics that really reached the renderer.

The context is advisory input to `evaluate_scientific_plot_policy.py`. It does not override schema validation or deterministic QA.
