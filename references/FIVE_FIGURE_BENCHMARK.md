# Five-Figure Engineering Benchmark

This local extension exercises the real SciPlot CLI on deterministic synthetic, inline JSON fixtures. No user papers, private measurement files, network services, or desktop plotting applications are needed. The data are engineering fixtures, not experiments; uncertainty values are explicitly synthetic standard deviations rather than inferred significance.

## Cases

1. Two line series with different colors and line styles.
2. Scatter points with marker sizing and alpha.
3. A continuous uncertainty band with sampled error bars and explicit SD semantics.
4. Grouped bars with two series and a legend.
5. Filled contours with a colorbar and panel annotation.

All cases request PNG, SVG, and PDF explicitly. This overrides the automatic contour format choice only for the benchmark; it does not change the general output policy. The vector gate still applies. No raster-image substitution is used to bypass a failed vector audit.

## Run

From the skill root, using Python 3.14:

```powershell
py -3.14 scripts/benchmark_five_figures.py --profile standard --out-dir <new-baseline-directory>
py -3.14 scripts/benchmark_five_figures.py --profile standard --out-dir <new-fixed-directory> --compare <baseline-directory>
py -3.14 scripts/benchmark_five_figures.py --profile audit --out-dir <new-audit-directory> --compare <baseline-directory>
```

Use `standard` only for the controlled working-project comparison. Use `audit` for final benchmark delivery: it retains bundle locks, environment records, attestation, portable runtime, checksums, and independent bundle verification. A standard pass is never described as full audit closure.

An existing nonempty output directory is rejected rather than overwritten. Each run retains source JSON, child command lines, stdout/stderr, elapsed render and validation times, quality status, export hashes, and `contact_sheet.png`. `benchmark.json` is the machine-readable result; a failing case makes the process fail.

Success requires all three actual exports, successful CLI status, semantic and vector QA, and a separate `sciplot.py validate` subprocess. Missing evidence is not a pass. The exact profile-specific export paths are used rather than searching for an arbitrary matching filename.

## Comparison and visual review

Compare like-for-like profile runs for timing; separately report validation time. Do not claim a performance improvement from one noisy run or compare the audit profile's overhead with a standard render as if they were the same task.

- `input_identical`: the full source JSON has the same SHA-256.
- `plot_data_identical`: all declared plot objects, including their data and plot styles, are equal.
- `png_identical`: exact PNG file equality. This proves repeatability only, not similarity to an independent published reference.

Comparison fields are informational, not acceptance gates. They compare against the previous report's recorded hashes; independently rehash both runs' files before making a final equality claim, particularly if earlier artifacts might have been changed.

Input hashes describe actual file bytes, including platform-specific line endings. Cross-platform input hashes or PNG bytes need not match even when the declared plot objects are equal; use `plot_data_identical` for that narrower comparison and do not turn byte differences into claims of changed scientific data.

For separately labeled presentation improvements, add `--polished`. This moves the grouped-bar legend away from bars, uses integer group ticks, and gives the contour panel label adequate contrast. It changes no plot data. Keep an unchanged-input control run as well; do not merge presentation changes into a claim of unchanged inputs or exact pixel stability.

Inspect the contact sheet and full-resolution figures after running. Outer-margin checks do not prove that interior labels never overlap. Human-readable scientific meaning, uncertainty declarations, and reference fidelity still require their own evidence.

## Limits

Benchmark reports retain absolute command paths, the skill root, and environment details for local reproducibility. Review or redact those fields before publishing reports from a personal machine. CI may archive its own public synthetic runs; that does not authorize uploading unrelated local benchmark directories or private files.

No SSIM against a self-generated render is presented as paper-reproduction accuracy. A source-free audit manifest may legitimately say `semantic_validated_pass`; it must not be promoted to `semantic_strict_pass` or visual strict reproduction. Generic replacement-data support is not proven unless the separate data-swap contract and changed-input proof are run.
