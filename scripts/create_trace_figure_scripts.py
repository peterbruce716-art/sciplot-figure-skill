from __future__ import annotations

import argparse
from pathlib import Path


TEMPLATE = '''from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[{root_parents}]
TRACE_SCRIPT = Path({trace_script!r})
SOURCE = ROOT / {source!r}
OUT_DIR = ROOT / {out_dir!r}
STEM = {stem!r}


def load_trace_module():
    spec = importlib.util.spec_from_file_location("trace_image_primitives", TRACE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load trace module: {{TRACE_SCRIPT}}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    trace = load_trace_module()
    manifest = trace.trace_image(SOURCE, OUT_DIR, STEM)
    manifest["per_figure_script"] = str(Path(__file__).relative_to(ROOT))
    manifest_path = OUT_DIR / f"{{STEM}}_per_figure_trace_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "visual_trace_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def create_script(*, source: Path, script_path: Path, root: Path, out_dir: Path, stem: str, trace_script: Path) -> Path:
    rel_source = source if not source.is_absolute() else source.relative_to(root)
    rel_out = out_dir if not out_dir.is_absolute() else out_dir.relative_to(root)
    try:
        parents = len(script_path.resolve().relative_to(root.resolve()).parents) - 1
    except ValueError:
        parents = 2
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        TEMPLATE.format(
            root_parents=max(parents, 1),
            trace_script=str(trace_script),
            source=rel_source.as_posix(),
            out_dir=rel_out.as_posix(),
            stem=stem,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return script_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create one runnable trace script for one source figure.")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--script", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--stem", required=True)
    parser.add_argument("--trace-script", required=True, type=Path)
    args = parser.parse_args()
    path = create_script(
        source=args.source,
        script_path=args.script,
        root=args.root,
        out_dir=args.out_dir,
        stem=args.stem,
        trace_script=args.trace_script,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
