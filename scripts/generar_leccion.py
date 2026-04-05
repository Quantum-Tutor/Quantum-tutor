from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from learning_content import generate_micro_lesson


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera una micro-leccion markdown desde el curriculum.")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    lesson = generate_micro_lesson(args.node_id)
    if args.output:
        Path(args.output).write_text(lesson, encoding="utf-8")
        return
    print(lesson)


if __name__ == "__main__":
    main()
