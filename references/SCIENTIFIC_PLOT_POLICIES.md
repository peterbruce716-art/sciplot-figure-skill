# Scientific Plot Policies

Policies live in `policies/scientific-plot-policy-v1.json` and are evaluated by `evaluate_scientific_plot_policy.py`. Each policy has an ID, severity, condition list, message, and recommended actions. Conditions are declarative and evaluated against a JSON context.

Policies are configurable: `--disable policy_id` turns off one rule and `--severity policy_id=warning` overrides its severity for a run. Warnings do not fail a render. Errors identify deterministic blockers such as missing glyphs or clipped text. The report records every disabled rule and the evaluation context.
