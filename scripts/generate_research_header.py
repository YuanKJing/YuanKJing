#!/usr/bin/env python3
"""Generate the restrained animated research-loop header used by README.md."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "research-loop.gif"
WIDTH = 1200
HEIGHT = 260
FRAME_COUNT = 60
FRAME_DELAY = 8
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/HelveticaNeue.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
)
FONT = next((candidate for candidate in FONT_CANDIDATES if candidate.exists()), None)

POINTS = (
    (240.0, 143.0),
    (600.0, 143.0),
    (960.0, 143.0),
    (960.0, 226.0),
    (240.0, 226.0),
    (240.0, 143.0),
)


def segment_lengths() -> list[float]:
    return [
        math.dist(POINTS[index], POINTS[index + 1])
        for index in range(len(POINTS) - 1)
    ]


LENGTHS = segment_lengths()
TOTAL_LENGTH = sum(LENGTHS)
NODE_DISTANCES = (0.0, LENGTHS[0], LENGTHS[0] + LENGTHS[1])


def point_at(distance: float) -> tuple[float, float]:
    remaining = distance % TOTAL_LENGTH
    for index, length in enumerate(LENGTHS):
        if remaining <= length:
            start_x, start_y = POINTS[index]
            end_x, end_y = POINTS[index + 1]
            ratio = remaining / length if length else 0.0
            return (
                start_x + (end_x - start_x) * ratio,
                start_y + (end_y - start_y) * ratio,
            )
        remaining -= length
    return POINTS[0]


def cyclic_distance(left: float, right: float) -> float:
    direct = abs(left - right)
    return min(direct, TOTAL_LENGTH - direct)


def node_strength(progress: float, node_distance: float) -> float:
    distance = cyclic_distance(progress, node_distance)
    return 0.18 + 0.82 * math.exp(-((distance / 118.0) ** 2))


def frame_svg(frame: int) -> str:
    progress = TOTAL_LENGTH * frame / FRAME_COUNT
    pulse_x, pulse_y = point_at(progress)
    trail_one_x, trail_one_y = point_at(progress - 22.0)
    trail_two_x, trail_two_y = point_at(progress - 44.0)
    strengths = [node_strength(progress, distance) for distance in NODE_DISTANCES]

    nodes = (
        (120, "PERCEPTION", "observe &amp; encode"),
        (480, "WORLD MODEL", "predict &amp; reason"),
        (840, "ACTION", "plan &amp; interact"),
    )
    node_markup = []
    for index, (x, title, subtitle) in enumerate(nodes):
        strength = strengths[index]
        border_opacity = 0.25 + 0.75 * strength
        fill_opacity = 0.07 + 0.09 * strength
        node_markup.append(
            f"""
            <rect x="{x}" y="103" width="240" height="80" rx="12"
                  fill="#73A9B5" fill-opacity="{fill_opacity:.3f}"
                  stroke="#73A9B5" stroke-opacity="{border_opacity:.3f}"
                  stroke-width="1.5"/>
            <circle cx="{x + 28}" cy="127" r="4.5"
                    fill="#D7AA67" fill-opacity="{border_opacity:.3f}"/>
            <text x="{x + 120}" y="139" text-anchor="middle"
                  fill="#F4F1E9" font-size="17" font-weight="600"
                  letter-spacing="1.8">{title}</text>
            <text x="{x + 120}" y="163" text-anchor="middle"
                  fill="#9CB3BC" font-size="13" letter-spacing="0.5">{subtitle}</text>
            """
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}"
     viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <linearGradient id="background" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0A1724"/>
      <stop offset="0.58" stop-color="#10283A"/>
      <stop offset="1" stop-color="#0B1B29"/>
    </linearGradient>
    <radialGradient id="pulse">
      <stop offset="0" stop-color="#F7D69C" stop-opacity="1"/>
      <stop offset="0.35" stop-color="#D7AA67" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#D7AA67" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="{WIDTH}" height="{HEIGHT}" rx="16" fill="url(#background)"/>

  <g stroke="#8CA8B2" stroke-opacity="0.055" stroke-width="1">
    <path d="M80 0V260 M160 0V260 M240 0V260 M320 0V260 M400 0V260
             M480 0V260 M560 0V260 M640 0V260 M720 0V260 M800 0V260
             M880 0V260 M960 0V260 M1040 0V260 M1120 0V260"/>
    <path d="M0 52H1200 M0 104H1200 M0 156H1200 M0 208H1200"/>
  </g>

  <text x="600" y="38" text-anchor="middle" fill="#7FA7B2"
        font-family="Helvetica, Arial, sans-serif" font-size="12"
        font-weight="600" letter-spacing="4">RESEARCH LOOP</text>
  <text x="600" y="70" text-anchor="middle" fill="#E7E4DB"
        font-family="Helvetica, Arial, sans-serif" font-size="18"
        font-weight="400" letter-spacing="1">
    learning systems that observe, predict, and act
  </text>

  <g fill="none" stroke="#7FA7B2" stroke-opacity="0.34" stroke-width="1.4">
    <path d="M360 143H480"/>
    <path d="M720 143H840"/>
    <path d="M960 183V214Q960 226 948 226H252Q240 226 240 214V183"/>
  </g>
  <g fill="#7FA7B2" fill-opacity="0.55">
    <path d="M475 138L485 143L475 148Z"/>
    <path d="M835 138L845 143L835 148Z"/>
    <path d="M235 188L240 178L245 188Z"/>
  </g>
  <text x="600" y="246" text-anchor="middle" fill="#718E99"
        font-family="Helvetica, Arial, sans-serif" font-size="11"
        letter-spacing="2.6">FEEDBACK</text>

  <g>
    <circle cx="{trail_two_x:.2f}" cy="{trail_two_y:.2f}" r="3"
            fill="#D7AA67" fill-opacity="0.16"/>
    <circle cx="{trail_one_x:.2f}" cy="{trail_one_y:.2f}" r="4"
            fill="#D7AA67" fill-opacity="0.34"/>
    <circle cx="{pulse_x:.2f}" cy="{pulse_y:.2f}" r="16" fill="url(#pulse)"/>
    <circle cx="{pulse_x:.2f}" cy="{pulse_y:.2f}" r="4.2" fill="#F7D69C"/>
  </g>

  <g font-family="Helvetica, Arial, sans-serif">
    {''.join(node_markup)}
  </g>
</svg>
"""


def main() -> None:
    magick = shutil.which("magick")
    if magick is None:
        raise SystemExit("ImageMagick is required: install it and rerun this script.")
    if FONT is None:
        raise SystemExit(
            "No supported font was found. Install DejaVu Sans and rerun this script."
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-header-") as temp_dir:
        temp = Path(temp_dir)
        frames: list[Path] = []
        for frame in range(FRAME_COUNT):
            svg_path = temp / f"frame-{frame:03d}.svg"
            png_path = temp / f"frame-{frame:03d}.png"
            svg_path.write_text(frame_svg(frame), encoding="utf-8")
            subprocess.run(
                [
                    magick,
                    "-background",
                    "none",
                    "-font",
                    str(FONT),
                    str(svg_path),
                    str(png_path),
                ],
                check=True,
            )
            frames.append(png_path)

        subprocess.run(
            [
                magick,
                *map(str, frames),
                "-set",
                "delay",
                str(FRAME_DELAY),
                "-loop",
                "0",
                "-colors",
                "128",
                "-layers",
                "Optimize",
                str(OUTPUT),
            ],
            check=True,
        )

    print(f"Generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
