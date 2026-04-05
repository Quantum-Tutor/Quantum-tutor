from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from learning_content import generate_exercises


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera ejercicios cuanticos parametrizados.")
    parser.add_argument("--tema", required=True)
    parser.add_argument("--dificultad", default="medium")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    payload = {
        "tema": args.tema,
        "dificultad": args.dificultad,
        "count": args.count,
        "ejercicios": generate_exercises(args.tema, args.dificultad, args.count),
    }

    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        return
    print(rendered)


if __name__ == "__main__":
    main()
