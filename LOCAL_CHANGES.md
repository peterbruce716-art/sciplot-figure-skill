# Locally Verified Extension

Upstream: `peterbruce716-art/sciplot-figure-skill`.
Pinned source commit: `425f0f3de2592cced489170101f772f6b81073a1`.
Upstream declared version: `2.10.1`.
Local patch identifier: `five-figure-validation-20260908`.

These integration notes describe changes based on the pinned revision, not a new versioned release. Repository history and the CI results for the exact commit determine publication and validation status.

## Changes

- Recover labeled errorbar series from the actual Matplotlib `ErrorbarContainer` during semantic extraction. The container's child line has an internal no-legend label; relying on that child alone falsely fails valid labeled errorbars. Numeric geometry, hashes, comparison thresholds, and provenance rejection are unchanged.
- Add eight uncertainty regression tests, including real artist extraction and negative controls for changed geometry, labels, hashes, and declared-only critical numeric provenance. The upstream label-provenance policy is unchanged; do not claim that every possible field is provenance-gated.
- Fix Windows newline translation in a synthetic tabular test fixture and add 18 CSV/TSV newline-preservation subcases. The production data loader is unchanged; actual field newlines remain intact.
- Add a deterministic five-figure CLI benchmark with exact export paths, independent validation, immutable run directories, PNG/SVG/PDF artifacts, quality status, hashes, timing, contact sheets, and baseline comparison.
- Add a separate presentation-review option for the bar legend, group ticks, and contour label contrast without changing plot data.

See `references/FIVE_FIGURE_BENCHMARK.md` for commands and evidence limits. Synthetic source-free QA is not paper-image fidelity, experimental accuracy, arbitrary data-swap support, or a claim of publication readiness.

## Function-Preserving Simplification

Local extension identifier: `function-preserving-simplification` (on top of the five-figure patch).

- Quick/standard generation and revalidation share one quality-check collector and decision function. Generation retains its separate render gate; standard generation and validation retain manifest/checksum verification.
- Command help and parser routing load only lightweight modules. Rendering, data loading, and quality-check dependencies are imported by the code paths that use them.
- The entrypoint omits duplicate workflow and common-mistake explanations while retaining protocol links, source/representation rules, scientific invariants, command routes, and status definitions.
- No legacy command, protocol, schema, renderer, digitizer, Advisor, data-swap, or bundle module is removed. Six new evaluation tests cover profile gates, return contracts, and dependency-free help.

## Cross-Platform CI Follow-Up

- Preserve the existing CI jobs and add complete unittest discovery plus standard and polished audit five-figure runs on Ubuntu and Windows.
- Build derived error-band paths from the already-resolved output root. This handles relative directories and Windows short-path aliases without changing derived values, source hashes, or scientific checks.
- Compare CLI project paths against their resolved form in the audit routing test, matching the existing CLI contract rather than a platform-dependent spelling.
- Add a regression requiring relative and resolved output directories to produce identical specifications and materialization reports.
