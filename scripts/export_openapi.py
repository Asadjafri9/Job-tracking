"""Export the authoritative FastAPI OpenAPI document as stable JSON."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/openapi.json"))
    arguments = parser.parse_args()
    schema = app.openapi()
    rendered = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
