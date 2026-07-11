from __future__ import annotations

import argparse
import importlib
import json
import shutil
import sys
from pathlib import Path

from matplotlib import font_manager


def module_version(name: str) -> str | None:
    try:
        module = importlib.import_module(name)
    except Exception:
        return None
    return str(getattr(module, "__version__", "installed"))


def font_available(name: str) -> bool:
    try:
        resolved = font_manager.findfont(name, fallback_to_default=False)
    except Exception:
        return False
    return Path(resolved).exists()


def check_environment() -> dict[str, object]:
    candidates = ["Arial", "Liberation Sans", "DejaVu Sans", "STIXGeneral", "STIX Two Text"]
    fonts = {name: font_available(name) for name in candidates}
    required = {
        "matplotlib": module_version("matplotlib"),
        "numpy": module_version("numpy"),
        "PIL": module_version("PIL"),
        "skimage": module_version("skimage"),
        "pypdf": module_version("pypdf"),
        "jsonschema": module_version("jsonschema"),
    }
    optional = {
        "pandas": module_version("pandas"),
        "openpyxl": module_version("openpyxl"),
        "pydantic": module_version("pydantic"),
    }
    missing_required = [name for name, version in required.items() if version is None]
    return {
        "schema": "scientificfigure.environment.v1",
        "python": sys.version.split()[0],
        "executable_role": "python",
        "required_modules": required,
        "optional_modules": optional,
        "fonts_available": fonts,
        "r_available": shutil.which("Rscript") is not None,
        "status": "pass" if not missing_required and any(fonts.values()) else "failed",
        "missing_required": missing_required,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check scientific figure reproduction runtime dependencies and fonts.")
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = check_environment()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
