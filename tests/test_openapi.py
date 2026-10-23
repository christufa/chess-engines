import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_docs_openapi_is_current():
    spec = importlib.util.spec_from_file_location("export_openapi", ROOT / "scripts" / "export_openapi.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    committed = (ROOT / "docs" / "openapi.json").read_text(encoding="utf-8")
    assert committed == module.openapi(), "run: uv run python scripts/export_openapi.py"
