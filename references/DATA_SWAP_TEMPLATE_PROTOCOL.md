# Data-Swap Template Protocol

Every reproduced figure that is intended to be reused must ship a
`scientificfigure.data-swap-template.v1` manifest.  A PDF trace is not a
data-swap template: it is bound to the reference image and must remain a
separate visual-trace artifact.

The template manifest must contain:

- `renderer_entrypoint`: a project-relative renderer entry point;
- one `figures.<id>` record per figure;
- `data_schema`: the complete, figure-specific schema or validation artifact;
- `example_data`: a valid example payload that can be rendered;
- `renderer`: the executable renderer for the figure;
- `outputs`: the declared `png`, `svg`, and/or `pdf` outputs;
- `historical_data_consumed: false` and an explicit `input_mode`.

The renderer interface is:

```text
python render_one.py --figure <id> --data <replacement-data> \
  --out-dir <isolated-output> --input-mode user_supplied
```

The renderer must validate the complete figure-specific shape before drawing,
write outputs outside the data directory, and emit a
`scientificfigure.data-swap-run.v1` manifest with input and output SHA-256
hashes.  User-supplied replacement data must not retain a PDF provenance claim.

Use `scripts/validate_data_swap_template.py` before delivery and
`scripts/run_data_swap.py` for an isolated run.  A template is not complete
until the example data renders, the output manifest is valid, and a second run
with a changed input produces a changed output hash.  The check is a required
contract gate; it does not infer a renderer for an arbitrary figure.
