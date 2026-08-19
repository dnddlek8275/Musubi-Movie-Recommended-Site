from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


def dashed_line(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], *, fill: str, width: int = 2, dash: int = 5, gap: int = 4) -> None:
    for start, end in zip(points, points[1:]):
        x1, y1 = start
        x2, y2 = end
        dx = x2 - x1
        dy = y2 - y1
        length = max(abs(dx), abs(dy))
        if length == 0:
            continue
        step = dash + gap
        for offset in range(0, length, step):
            segment_end = min(offset + dash, length)
            sx = round(x1 + dx * offset / length)
            sy = round(y1 + dy * offset / length)
            ex = round(x1 + dx * segment_end / length)
            ey = round(y1 + dy * segment_end / length)
            draw.line((sx, sy, ex, ey), fill=fill, width=width)


def copy_strip(image: Image.Image, source_box: tuple[int, int, int, int], destination: tuple[int, int]) -> None:
    image.paste(image.crop(source_box), destination)


def fix_diagram(source: Path, destination: Path) -> None:
    image = Image.open(source).convert("RGB")

    # 기존 DB Primary/Standby 연결 점선을 인접 배경으로 복원한다.
    # 좌표는 1672x941 원본 구조도 기준이다.
    copy_strip(image, (379, 714, 387, 855), (367, 714))
    copy_strip(image, (1229, 714, 1237, 855), (1217, 714))
    copy_strip(image, (365, 841, 649, 849), (365, 851))
    copy_strip(image, (998, 841, 1228, 849), (998, 851))

    draw = ImageDraw.Draw(image)
    line_color = "#777777"

    # Internal AI HA Group은 DB가 아니라 GPU AI A/B 대상으로 연결한다.
    dashed_line(draw, [(143, 716), (143, 853), (644, 853)], fill=line_color)
    dashed_line(draw, [(1003, 716), (1003, 853)], fill=line_color)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="CineVerse 물리 구조도의 Internal AI HA 점선 연결을 수정합니다.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    fix_diagram(args.source, args.destination)


if __name__ == "__main__":
    main()
