# Data Swap Protocol

When a project renderer is intended to be reused with replacement measurements,
keep data and rendering code separate. A data-swap run must:

1. Put the replacement payload in a new, isolated data directory.
2. Preserve the figure-specific schema and set `historical_data_consumed` to
   `false`.
3. Declare `input_mode` as `fresh_digitization` for values digitized from the
   current source or `user_supplied` for replacement values. Do not retain a
   PDF provenance claim for values that were manually replaced.
4. Validate the complete shape required by the selected renderer before
   importing it.
5. Write outputs to a new or empty directory outside the input data directory
   and emit a run manifest containing input/output SHA-256 hashes.

Project-specific renderers may implement the contract with a `render_one.py`
entry point. A canonical batch rebuild that regenerates source crops or fresh
measurements must remain a separate command; it must never be used for an
alternate-data experiment because it can overwrite the canonical source set.

The data-swap manifest should use `scientificfigure.data-swap-run.v1` (or a
project-namespaced equivalent), retain relative paths where possible, and
record the renderer figure ID, data schema, input mode, historical-data flag,
output paths, and hashes. The generic runner independently recalculates the
input hash and every declared output hash; renderer-reported hashes are never
the only evidence. Output paths must be portable relative paths, must remain
inside the isolated output directory after resolution, and must not resolve
through symlinks into the input data directory or outside the project contract.
A changed input must produce a changed output or the template must explicitly
declare and justify invariant outputs.

When dispatched through `scripts/run_data_swap.py`, renderer stdout/stderr must
be treated as logs, not validation evidence. The runner captures them under
`runner_logs/` and keeps its own stdout as a single JSON payload with stable
success or failure fields.
