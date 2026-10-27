"""Run: python -m parking.crops_cli LAT LON [count]  -- fetch sign crops from Mapillary and read them."""
import sys

from PIL import Image

from .mapillary import sign_crops
from .signs import read_sign, to_rules


def main() -> None:
    lat, lon = float(sys.argv[1]), float(sys.argv[2])
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    for p in sign_crops(lat, lon, count=n):
        s = read_sign(Image.open(p))
        print(f"\n== {p.name} ({Image.open(p).size})")
        print(f"  text: {s['transcription']!r} legible={s['legible']}")
        for r in to_rules(s):
            print(f"  rule: {r.kind} days={sorted(r.days)} {r.start_min // 60:02d}:{r.start_min % 60:02d}-"
                  f"{r.end_min // 60:02d}:{r.end_min % 60:02d} limit={r.limit_min}")


if __name__ == "__main__":
    main()
