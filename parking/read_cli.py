"""Run: python -m parking.read_cli photos/*.jpg"""
import sys
from pathlib import Path

from .signs import read_photo


def main(paths: list[str]) -> None:
    for p in paths:
        print(f"\n== {p}")
        results = read_photo(Path(p))
        if not results:
            print("  no signs found")
        for r in results:
            s = r["sign"]
            print(f"  box={r['box']}")
            print(f"  text: {s['transcription']!r}  legible={s['legible']}")
            print(f"  rules: {r['rules']}")


if __name__ == "__main__":
    main(sys.argv[1:])
