from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np


def _readonly_float64(values: Sequence[float] | np.ndarray, *, ndim: int | None = None) -> np.ndarray:
    array = np.ascontiguousarray(values, dtype="<f8")
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"expected {ndim}-D geometry, got {array.ndim}-D")
    array.setflags(write=False)
    return array


def smooth_curve_points(
    x: Sequence[float] | np.ndarray,
    y: Sequence[float] | np.ndarray,
    *,
    samples_per_interval: int = 16,
    smoothing_window: int = 1,
    clip: tuple[float, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a deterministic, shape-preserving smooth curve from digitized points.

    A short reflected moving average removes raster stair-steps, then a PCHIP-style
    cubic Hermite interpolation preserves endpoint values and avoids overshoot at
    monotonic transitions.  This is intentionally NumPy-only so project renderers
    remain portable when SciPy is unavailable.
    """
    x_arr = np.asarray(x, dtype="<f8")
    y_arr = np.asarray(y, dtype="<f8")
    if x_arr.ndim != 1 or y_arr.ndim != 1 or x_arr.size != y_arr.size or x_arr.size < 2:
        raise ValueError("x and y must be one-dimensional arrays with at least two paired points")
    if not np.all(np.isfinite(x_arr)) or not np.all(np.isfinite(y_arr)):
        raise ValueError("x and y must contain only finite values")
    if np.any(np.diff(x_arr) <= 0):
        raise ValueError("x must be strictly increasing")
    if samples_per_interval < 1:
        raise ValueError("samples_per_interval must be positive")

    window = max(1, int(smoothing_window))
    if window > 1:
        if window % 2 == 0:
            window += 1
        radius = window // 2
        padded = np.pad(y_arr, (radius, radius), mode="reflect")
        kernel = np.full(window, 1.0 / window, dtype="<f8")
        filtered = np.convolve(padded, kernel, mode="valid")
        filtered[0] = y_arr[0]
        filtered[-1] = y_arr[-1]
    else:
        filtered = y_arr.copy()

    h = np.diff(x_arr)
    delta = np.diff(filtered) / h
    slopes = np.zeros_like(filtered)
    if filtered.size == 2:
        slopes[:] = delta[0]
    else:
        for index in range(1, filtered.size - 1):
            if delta[index - 1] * delta[index] <= 0:
                slopes[index] = 0.0
            else:
                w_left = 2.0 * h[index] + h[index - 1]
                w_right = h[index] + 2.0 * h[index - 1]
                slopes[index] = (w_left + w_right) / (w_left / delta[index - 1] + w_right / delta[index])
        slopes[0] = ((2.0 * h[0] + h[1]) * delta[0] - h[0] * delta[1]) / (h[0] + h[1])
        slopes[-1] = ((2.0 * h[-1] + h[-2]) * delta[-1] - h[-1] * delta[-2]) / (h[-1] + h[-2])
        if slopes[0] * delta[0] <= 0:
            slopes[0] = 0.0
        elif abs(slopes[0]) > 3.0 * abs(delta[0]):
            slopes[0] = 3.0 * delta[0]
        if slopes[-1] * delta[-1] <= 0:
            slopes[-1] = 0.0
        elif abs(slopes[-1]) > 3.0 * abs(delta[-1]):
            slopes[-1] = 3.0 * delta[-1]

    dense_x_parts: list[np.ndarray] = []
    dense_y_parts: list[np.ndarray] = []
    local_t = np.linspace(0.0, 1.0, int(samples_per_interval), endpoint=False, dtype="<f8")
    for index, width in enumerate(h):
        t = local_t
        t2 = t * t
        t3 = t2 * t
        basis0 = 2.0 * t3 - 3.0 * t2 + 1.0
        basis1 = t3 - 2.0 * t2 + t
        basis2 = -2.0 * t3 + 3.0 * t2
        basis3 = t3 - t2
        dense_x_parts.append(x_arr[index] + width * t)
        dense_y_parts.append(basis0 * filtered[index] + basis1 * width * slopes[index] + basis2 * filtered[index + 1] + basis3 * width * slopes[index + 1])
    dense_x = np.concatenate([*dense_x_parts, x_arr[-1:]])
    dense_y = np.concatenate([*dense_y_parts, filtered[-1:]])
    if clip is not None:
        dense_y = np.clip(dense_y, float(clip[0]), float(clip[1]))
    return dense_x, dense_y


def _source_hash(kind: str, arrays: Iterable[np.ndarray]) -> str:
    digest = hashlib.sha256()
    digest.update(f"sciplot.shared_geometry.v1:{kind}".encode("ascii"))
    for array in arrays:
        digest.update(str(array.shape).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return f"sha256:{digest.hexdigest()}"


def _tag_artist(artist: Any, source_id: str, source_hash: str, role: str, **extra: Any) -> Any:
    artist._sciplot_geometry_source_id = source_id
    artist._sciplot_geometry_source_hash = source_hash
    artist._sciplot_geometry_role = role
    for key, value in extra.items():
        setattr(artist, f"_sciplot_{key}", value)
    return artist


@dataclass(frozen=True)
class SharedSeries:
    """Immutable curve data reused by lines, segments, markers, and fills."""

    source_id: str
    x: Sequence[float] | np.ndarray = field(repr=False)
    y: Sequence[float] | np.ndarray = field(repr=False)
    source_hash: str = field(init=False)

    def __post_init__(self) -> None:
        x = _readonly_float64(self.x, ndim=1)
        y = _readonly_float64(self.y, ndim=1)
        if not self.source_id:
            raise ValueError("source_id must not be empty")
        if x.size != y.size or x.size < 2:
            raise ValueError("x and y must have the same length and at least two points")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "source_hash", _source_hash("series", (x, y)))

    def plot(self, ax: Any, **kwargs: Any) -> Any:
        (artist,) = ax.plot(self.x, self.y, **kwargs)
        return _tag_artist(artist, self.source_id, self.source_hash, "curve")

    def plot_segments(self, ax: Any, slices: Iterable[slice | tuple[int, int]], **kwargs: Any) -> list[Any]:
        artists = []
        for part_index, part in enumerate(slices):
            view = part if isinstance(part, slice) else slice(part[0], part[1])
            (artist,) = ax.plot(self.x[view], self.y[view], **kwargs)
            artists.append(
                _tag_artist(
                    artist,
                    self.source_id,
                    self.source_hash,
                    "curve_segment",
                    geometry_part_index=part_index,
                )
            )
        return artists

    def fill_between(
        self,
        ax: Any,
        lower: "SharedSeries | float | Sequence[float] | np.ndarray",
        **kwargs: Any,
    ) -> Any:
        if isinstance(lower, SharedSeries):
            if lower.x.shape != self.x.shape or not np.array_equal(lower.x, self.x):
                raise ValueError("fill boundaries must share the same x coordinates")
            lower_y = lower.y
            boundary_ids = [self.source_id, lower.source_id]
            boundary_hashes = [self.source_hash, lower.source_hash]
        elif np.isscalar(lower):
            lower_y = np.full_like(self.y, float(lower))
            boundary_ids = [self.source_id]
            boundary_hashes = [self.source_hash]
        else:
            lower_y = _readonly_float64(lower, ndim=1)
            if lower_y.shape != self.y.shape:
                raise ValueError("lower fill boundary must match the curve length")
            boundary_ids = [self.source_id]
            boundary_hashes = [self.source_hash]
        artist = ax.fill_between(self.x, self.y, lower_y, **kwargs)
        return _tag_artist(
            artist,
            self.source_id,
            self.source_hash,
            "fill_between",
            boundary_source_ids=boundary_ids,
            boundary_source_hashes=boundary_hashes,
        )


@dataclass(frozen=True)
class SharedPathGeometry:
    """Immutable compound path used once for both local fill and boundary."""

    source_id: str
    vertices: Sequence[Sequence[float]] | np.ndarray = field(repr=False)
    codes: Sequence[int] | np.ndarray = field(repr=False)
    source_hash: str = field(init=False)

    def __post_init__(self) -> None:
        vertices = _readonly_float64(self.vertices, ndim=2)
        codes = np.ascontiguousarray(self.codes, dtype=np.uint8)
        codes.setflags(write=False)
        if vertices.shape[1:] != (2,) or vertices.shape[0] != codes.shape[0]:
            raise ValueError("vertices must be N x 2 and codes must have length N")
        if not self.source_id:
            raise ValueError("source_id must not be empty")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "codes", codes)
        object.__setattr__(self, "source_hash", _source_hash("path", (vertices, codes)))

    def mpl_path(self) -> Any:
        from matplotlib.path import Path as MplPath

        return MplPath(self.vertices, self.codes)

    def patch(self, ax: Any, **kwargs: Any) -> Any:
        from matplotlib.patches import PathPatch

        artist = PathPatch(self.mpl_path(), **kwargs)
        ax.add_patch(artist)
        return _tag_artist(artist, self.source_id, self.source_hash, "compound_path")


def _iter_tagged_artists(figure: Any) -> Iterable[Any]:
    for ax in figure.axes:
        for artist in [*ax.lines, *ax.collections, *ax.patches]:
            if hasattr(artist, "_sciplot_geometry_source_id"):
                yield artist


def audit_shared_geometry(figure: Any) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    failures: list[str] = []
    artist_count = 0
    for artist in _iter_tagged_artists(figure):
        artist_count += 1
        source_id = str(artist._sciplot_geometry_source_id)
        source_hash = str(artist._sciplot_geometry_source_hash)
        record = sources.setdefault(source_id, {"hashes": set(), "roles": [], "artist_count": 0})
        record["hashes"].add(source_hash)
        record["roles"].append(str(artist._sciplot_geometry_role))
        record["artist_count"] += 1
        boundary_ids = getattr(artist, "_sciplot_boundary_source_ids", [])
        boundary_hashes = getattr(artist, "_sciplot_boundary_source_hashes", [])
        if len(boundary_ids) != len(boundary_hashes):
            failures.append(f"{source_id}: fill boundary ids/hashes length mismatch")
        for boundary_id, boundary_hash in zip(boundary_ids, boundary_hashes):
            boundary_id = str(boundary_id)
            boundary_hash = str(boundary_hash)
            boundary_record = sources.setdefault(
                boundary_id,
                {"hashes": set(), "roles": [], "artist_count": 0},
            )
            boundary_record["hashes"].add(boundary_hash)
            boundary_record["roles"].append("fill_boundary")
            if boundary_id != source_id:
                boundary_record["artist_count"] += 1
    for source_id, record in sources.items():
        if len(record["hashes"]) != 1:
            failures.append(f"{source_id}: one logical source resolved to multiple geometry hashes")
    serializable = {
        source_id: {
            "source_hash": sorted(record["hashes"])[0] if len(record["hashes"]) == 1 else None,
            "roles": sorted(set(record["roles"])),
            "artist_count": record["artist_count"],
        }
        for source_id, record in sorted(sources.items())
    }
    if artist_count == 0:
        failures.append("no shared-geometry artists were found")
    return {
        "schema": "sciplot.shared_geometry.audit.v1",
        "status": "pass" if not failures else "failed",
        "artist_count": artist_count,
        "source_count": len(sources),
        "sources": serializable,
        "failures": failures,
    }


def write_shared_geometry_report(figure: Any, path: Path) -> dict[str, Any]:
    report = audit_shared_geometry(figure)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report
