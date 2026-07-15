# Data Profiling Contract

`data-profile-v1.schema.json` is the stable machine-readable contract. The profiler supports CSV, TSV, XLSX, XLSM, and XLS input through pandas and emits UTF-8 JSON with a source filename and SHA-256. It does not mutate the input.

Inference is intentionally conservative: numeric columns are continuous unless integer cardinality is low, object columns are datetime only when parsing is high-confidence, and low-cardinality text is categorical. Ambiguity is a warning, not a silent coercion. A suspected identifier is reported so it is not accidentally plotted as a measurement.

All data-dependent claims must be checked against the original experimental design. IQR outlier counts are screening information, not a license to remove observations.
