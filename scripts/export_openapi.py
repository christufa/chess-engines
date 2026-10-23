"""Write the API's OpenAPI document to docs/openapi.json (CI checks it is current).

    uv run python scripts/export_openapi.py
"""

import json
from pathlib import Path

from chess_engines.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def openapi() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    (ROOT / "docs" / "openapi.json").write_text(openapi(), encoding="utf-8", newline="\n")
