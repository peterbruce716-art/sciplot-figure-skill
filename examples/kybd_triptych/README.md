# KYBD Triptych Grouped-Bar Example

This example reconstructs a three-panel grouped-bar figure from a fresh digitization of the supplied raster reference. The public bundle contains only the derived data and calibration evidence; the original reference image is intentionally omitted.

The original reference image is not included in the open-source package. For a local fidelity run, provide the user-supplied reference image separately:

```powershell
py -3.14 scripts\run_reproduction.py `
  --spec examples\kybd_triptych\visualspec.json `
  --source path\to\reference.png `
  --out-dir out\kybd_triptych `
  --require-strict
```

The reconstruction mode is `digitized_raster` with `semantic_vector` output. Values are raster-derived estimates, not recovered primary measurements. Error-bar spans are freshly detected from locally contrasting cap/stem pixels and reproduced as visual extents only; the image does not establish whether they mean SD, SEM, CI, or another statistic. Pixel-level uncertainty, error-bar detection geometry, and occlusion evidence are retained in `digitization_audit.json`. Panel P1 uses side-by-side bars; P2 uses centered nested bars; P3 uses a light outer bar with offset inner bars.
