from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from trading_environment import SCHEMA_VERSION, builtin_presets, validate_environment


DEFAULT_PRESET_PATH = Path("data/strategy_lab/built_in_presets.json")


def build_presets_payload() -> Dict[str, Any]:
    presets = builtin_presets()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "strategy_lab_presets",
        "preset_count": len(presets),
        "disclaimer": (
            "Built-in environments are simulation presets only. They do not change V8, "
            "place trades, connect to brokers, or provide investment advice."
        ),
        "presets": [
            {
                **preset,
                "validation": {
                    "errors": validate_environment(preset)[0],
                    "warnings": validate_environment(preset)[1],
                },
            }
            for preset in presets
        ],
    }


def write_builtin_presets(path: Path = DEFAULT_PRESET_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(build_presets_payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)
    return path


def load_builtin_presets(path: Path = DEFAULT_PRESET_PATH) -> List[Dict[str, Any]]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("presets", [])
    return build_presets_payload()["presets"]


if __name__ == "__main__":
    print(write_builtin_presets())
