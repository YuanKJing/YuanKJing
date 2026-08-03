#!/usr/bin/env python3
"""Generate the theme-aware research field-log visual used by README.md.

The visual is built from Junqi Jing's own public research materials: a formal
portrait and real dual-arm teleoperation footage. The source URLs are pinned
to a commit and verified before rendering.
"""

from __future__ import annotations

import base64
import functools
import hashlib
import math
import os
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

SOURCE_COMMIT = "2d1cbd701efb22f2a8d074b1b82f22bb04d04cbf"
SOURCE_ROOT = f"https://raw.githubusercontent.com/YuanKJing/JunqiJing/{SOURCE_COMMIT}"
SOURCES = {
    "portrait.jpg": (
        f"{SOURCE_ROOT}/content/authors/admin/avatar.jpg",
        "f2dcfd45c2d9baaaa79bcd3ed52e3eaf5dac3c2e46c158db4bc6dd4e845ecd8f",
    ),
    "teleoperation.mp4": (
        f"{SOURCE_ROOT}/static/videos/teleoperation.mp4",
        "f37131342022ab2d4159facabb485e5b4538d110e452debb9c3c6bd10f5af69c",
    ),
}

FRAME_RATE = 5
FRAME_COUNT = 24
FRAME_DELAY = round(100 / FRAME_RATE)
VIDEO_START_SECONDS = 7.5
POSTER_SOURCE_FRAME = 15


@dataclass(frozen=True)
class Theme:
    background: str
    surface: str
    surface_strong: str
    border: str
    grid: str
    ink: str
    muted: str
    accent: str
    image_overlay: str
    image_overlay_opacity: float


LIGHT = Theme(
    background="#F8FAFC",
    surface="#EEF3F7",
    surface_strong="#E2EAF1",
    border="#B8C5D1",
    grid="#1E3A5F",
    ink="#0F172A",
    muted="#52647A",
    accent="#A16207",
    image_overlay="#1E3A5F",
    image_overlay_opacity=0.04,
)

DARK = Theme(
    background="#08111B",
    surface="#0E1B2A",
    surface_strong="#14263A",
    border="#31506F",
    grid="#93A9BF",
    ink="#E8EEF5",
    muted="#9CB0C4",
    accent="#D6A64A",
    image_overlay="#07111C",
    image_overlay_opacity=0.16,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@functools.lru_cache(maxsize=None)
def image_data_uri(path: Path) -> str:
    mime_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }.get(path.suffix.lower())
    if mime_type is None:
        raise ValueError(f"Unsupported embedded image type: {path.suffix}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def fetch_sources(source_dir: Path) -> dict[str, Path]:
    source_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, (url, expected_hash) in SOURCES.items():
        destination = source_dir / name
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "YuanKJing-README-asset-generator/1.0"},
        )
        last_error: Exception | None = None
        for _ in range(3):
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    destination.write_bytes(response.read())
                last_error = None
                break
            except (OSError, TimeoutError) as error:
                last_error = error
                destination.unlink(missing_ok=True)
        if last_error is not None:
            raise SystemExit(f"Unable to download {name}: {last_error}")
        actual_hash = sha256(destination)
        if actual_hash != expected_hash:
            raise SystemExit(
                f"Checksum mismatch for {name}: expected {expected_hash}, "
                f"received {actual_hash}."
            )
        paths[name] = destination
    return paths


def load_local_sources(source_dir: Path) -> dict[str, Path]:
    aliases = {"portrait.jpg": "avatar.jpg"}
    paths: dict[str, Path] = {}
    for name, (_, expected_hash) in SOURCES.items():
        destination = source_dir / name
        if not destination.exists() and name in aliases:
            destination = source_dir / aliases[name]
        if not destination.is_file():
            raise SystemExit(f"Missing local source: {destination}")
        actual_hash = sha256(destination)
        if actual_hash != expected_hash:
            raise SystemExit(
                f"Checksum mismatch for {name}: expected {expected_hash}, "
                f"received {actual_hash}."
            )
        paths[name] = destination
    return paths


def extract_video_frames(ffmpeg: str, video: Path, frame_dir: Path) -> list[Path]:
    frame_dir.mkdir(parents=True)
    pattern = frame_dir / "frame-%03d.png"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            str(VIDEO_START_SECONDS),
            "-i",
            str(video),
            "-vf",
            f"crop=540:444:0:205,fps={FRAME_RATE}",
            "-frames:v",
            str(FRAME_COUNT),
            "-start_number",
            "0",
            str(pattern),
        ],
        check=True,
    )
    frames = sorted(frame_dir.glob("frame-*.png"))
    if len(frames) != FRAME_COUNT:
        raise SystemExit(f"Expected {FRAME_COUNT} video frames, found {len(frames)}.")
    return frames


def interpolate_polyline(
    points: tuple[tuple[float, float], ...], progress: float
) -> tuple[float, float]:
    progress = max(0.0, min(1.0, progress))
    lengths = [
        math.dist(points[index], points[index + 1]) for index in range(len(points) - 1)
    ]
    target = progress * sum(lengths)
    for index, length in enumerate(lengths):
        if target <= length or index == len(lengths) - 1:
            local = 0.0 if length == 0 else target / length
            start_x, start_y = points[index]
            end_x, end_y = points[index + 1]
            return (
                start_x + (end_x - start_x) * local,
                start_y + (end_y - start_y) * local,
            )
        target -= length
    return points[-1]


def common_defs(
    theme: Theme,
    portrait_clip: str,
    study_clip: str,
    robot_clip: str,
) -> str:
    return f"""
  <defs>
    <clipPath id="portrait-clip">{portrait_clip}</clipPath>
    <clipPath id="study-clip">{study_clip}</clipPath>
    <clipPath id="robot-clip">{robot_clip}</clipPath>
    <linearGradient id="robot-shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{theme.background}" stop-opacity="0.03"/>
      <stop offset="1" stop-color="{theme.background}" stop-opacity="0.42"/>
    </linearGradient>
    <radialGradient id="pulse" cx="50%" cy="50%" r="50%">
      <stop offset="0" stop-color="{theme.accent}" stop-opacity="0.88"/>
      <stop offset="1" stop-color="{theme.accent}" stop-opacity="0"/>
    </radialGradient>
  </defs>
"""


def number_badge(x: float, y: float, label: str, theme: Theme) -> str:
    return f"""
  <g transform="translate({x} {y})">
    <rect width="34" height="24" rx="12" fill="{theme.background}"
          fill-opacity="0.92" stroke="{theme.border}"/>
    <text x="17" y="16" text-anchor="middle" fill="{theme.ink}"
          font-family="Avenir Next, Helvetica Neue, Arial, sans-serif"
          font-size="10" font-weight="700" letter-spacing="0.8">{label}</text>
  </g>
"""


def desktop_svg(
    theme: Theme,
    portrait: Path,
    study_frames: tuple[Path, Path, Path],
    video_frame: Path,
    frame_index: int,
) -> str:
    width, height = 1200, 360
    progress = frame_index / max(1, FRAME_COUNT - 1)
    pulse_x, pulse_y = interpolate_polyline(
        ((248, 292), (320, 292), (706, 292), (792, 292), (1132, 292)),
        progress,
    )
    scan_y = 78 + 176 * (0.5 - 0.5 * math.cos(progress * math.pi))
    portrait_uri = image_data_uri(portrait)
    study_uris = tuple(image_data_uri(path) for path in study_frames)
    video_uri = image_data_uri(video_frame)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{
        common_defs(
            theme,
            '<rect x="36" y="36" width="238" height="288" rx="18"/>',
            '<rect x="292" y="36" width="448" height="288" rx="18"/>',
            '<rect x="758" y="36" width="406" height="288" rx="18"/>',
        )
    }
  <rect x="1" y="1" width="1198" height="358" rx="24"
        fill="{theme.background}" stroke="{theme.border}"/>

  <g stroke="{theme.grid}" stroke-opacity="0.075" stroke-width="1">
    <path d="M18 72H1182 M18 144H1182 M18 216H1182 M18 288H1182"/>
    <path d="M120 18V342 M240 18V342 M360 18V342 M480 18V342
             M600 18V342 M720 18V342 M840 18V342 M960 18V342 M1080 18V342"/>
  </g>

  <rect x="36" y="36" width="238" height="288" rx="18"
        fill="{theme.surface}"/>
  <image x="36" y="36" width="238" height="288"
         preserveAspectRatio="xMidYMid slice" href="{portrait_uri}"
         clip-path="url(#portrait-clip)"/>
  <rect x="36" y="36" width="238" height="288" rx="18"
        fill="{theme.image_overlay}" fill-opacity="{theme.image_overlay_opacity}"/>
  <path d="M58 302H252" stroke="{theme.background}" stroke-opacity="0.72"/>
  <rect x="36" y="36" width="238" height="288" rx="18"
        fill="none" stroke="{theme.border}"/>
  {number_badge(52, 52, "01", theme)}

  <rect x="292" y="36" width="448" height="288" rx="18"
        fill="{theme.surface}"/>
  <image x="310" y="54" width="132" height="184"
         preserveAspectRatio="xMinYMid slice" href="{study_uris[0]}"
         clip-path="url(#study-clip)"/>
  <image x="450" y="54" width="132" height="184"
         preserveAspectRatio="xMidYMid slice" href="{study_uris[1]}"
         clip-path="url(#study-clip)"/>
  <image x="590" y="54" width="132" height="184"
         preserveAspectRatio="xMaxYMid slice" href="{study_uris[2]}"
         clip-path="url(#study-clip)"/>
  <rect x="292" y="36" width="448" height="214" rx="18"
        fill="{theme.image_overlay}" fill-opacity="{theme.image_overlay_opacity}"/>
  <rect x="292" y="238" width="448" height="86"
        fill="{theme.surface_strong}" clip-path="url(#study-clip)"/>
  <g fill="none" stroke="{theme.grid}" stroke-opacity="0.40" stroke-width="1.2">
    <path d="M326 281 C374 249 414 310 462 275 S550 257 594 282 S662 304 706 268"/>
    <path d="M326 297H706" stroke-dasharray="3 7" stroke-opacity="0.24"/>
  </g>
  <g fill="{theme.muted}">
    <circle cx="326" cy="281" r="3"/><circle cx="391" cy="270" r="3"/>
    <circle cx="462" cy="275" r="3"/><circle cx="528" cy="267" r="3"/>
    <circle cx="594" cy="282" r="3"/><circle cx="652" cy="290" r="3"/>
    <circle cx="706" cy="268" r="3"/>
  </g>
  <rect x="292" y="36" width="448" height="288" rx="18"
        fill="none" stroke="{theme.border}"/>
  {number_badge(308, 52, "02", theme)}

  <rect x="758" y="36" width="406" height="288" rx="18"
        fill="{theme.surface}"/>
  <image x="758" y="36" width="406" height="288"
         preserveAspectRatio="xMidYMid slice" href="{video_uri}"
         clip-path="url(#robot-clip)"/>
  <rect x="758" y="36" width="406" height="288"
        fill="url(#robot-shade)" clip-path="url(#robot-clip)"/>
  <path d="M782 {scan_y:.1f}H1140" stroke="{theme.accent}"
        stroke-opacity="0.28" stroke-width="1"/>
  <path d="M801 58h-18v18 M1140 58h18v18 M801 302h-18v-18 M1140 302h18v-18"
        fill="none" stroke="{theme.ink}" stroke-opacity="0.52" stroke-width="1.4"/>
  <rect x="758" y="36" width="406" height="288" rx="18"
        fill="none" stroke="{theme.border}"/>
  {number_badge(774, 52, "03", theme)}

  <path d="M248 292H320 C420 292 610 292 706 292 H792 C904 292 1030 292 1132 292"
        fill="none" stroke="{theme.accent}" stroke-opacity="0.48"
        stroke-width="1.5" stroke-dasharray="4 7"/>
  <circle cx="248" cy="292" r="4" fill="{theme.accent}"/>
  <circle cx="706" cy="292" r="4" fill="{theme.accent}"/>
  <circle cx="1132" cy="292" r="4" fill="{theme.accent}"/>
  <circle cx="{pulse_x:.1f}" cy="{pulse_y:.1f}" r="16" fill="url(#pulse)"/>
  <circle cx="{pulse_x:.1f}" cy="{pulse_y:.1f}" r="3.5" fill="{theme.accent}"/>
</svg>
"""


def mobile_svg(
    theme: Theme,
    portrait: Path,
    study_frames: tuple[Path, Path, Path],
    video_frame: Path,
    frame_index: int,
) -> str:
    width, height = 720, 460
    progress = frame_index / max(1, FRAME_COUNT - 1)
    pulse_x, pulse_y = interpolate_polyline(
        ((130, 195), (130, 236), (255, 344), (306, 344), (658, 344)),
        progress,
    )
    scan_y = 74 + 252 * (0.5 - 0.5 * math.cos(progress * math.pi))
    portrait_uri = image_data_uri(portrait)
    study_uris = tuple(image_data_uri(path) for path in study_frames)
    video_uri = image_data_uri(video_frame)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{
        common_defs(
            theme,
            '<circle cx="130" cy="116" r="86"/>',
            '<rect x="24" y="224" width="232" height="212" rx="18"/>',
            '<rect x="274" y="24" width="422" height="412" rx="20"/>',
        )
    }
  <rect x="1" y="1" width="718" height="458" rx="24"
        fill="{theme.background}" stroke="{theme.border}"/>
  <g stroke="{theme.grid}" stroke-opacity="0.075" stroke-width="1">
    <path d="M18 92H702 M18 184H702 M18 276H702 M18 368H702"/>
    <path d="M90 18V442 M180 18V442 M270 18V442 M360 18V442
             M450 18V442 M540 18V442 M630 18V442"/>
  </g>

  <circle cx="130" cy="116" r="88" fill="{theme.surface}"/>
  <image x="42" y="28" width="176" height="176"
         preserveAspectRatio="xMidYMid slice" href="{portrait_uri}"
         clip-path="url(#portrait-clip)"/>
  <circle cx="130" cy="116" r="86" fill="{theme.image_overlay}"
          fill-opacity="{theme.image_overlay_opacity}"/>
  <circle cx="130" cy="116" r="87" fill="none" stroke="{theme.border}"/>
  {number_badge(40, 40, "01", theme)}

  <rect x="24" y="224" width="232" height="212" rx="18"
        fill="{theme.surface}"/>
  <image x="38" y="240" width="64" height="106"
         preserveAspectRatio="xMinYMid slice" href="{study_uris[0]}"
         clip-path="url(#study-clip)"/>
  <image x="108" y="240" width="64" height="106"
         preserveAspectRatio="xMidYMid slice" href="{study_uris[1]}"
         clip-path="url(#study-clip)"/>
  <image x="178" y="240" width="64" height="106"
         preserveAspectRatio="xMaxYMid slice" href="{study_uris[2]}"
         clip-path="url(#study-clip)"/>
  <rect x="24" y="224" width="232" height="132" rx="18"
        fill="{theme.image_overlay}" fill-opacity="{theme.image_overlay_opacity}"/>
  <rect x="24" y="350" width="232" height="86"
        fill="{theme.surface_strong}" clip-path="url(#study-clip)"/>
  <path d="M48 397 C83 370 112 414 146 387 S204 378 232 399"
        fill="none" stroke="{theme.grid}" stroke-opacity="0.42" stroke-width="1.3"/>
  <g fill="{theme.muted}">
    <circle cx="48" cy="397" r="3"/><circle cx="92" cy="388" r="3"/>
    <circle cx="146" cy="387" r="3"/><circle cx="191" cy="387" r="3"/>
    <circle cx="232" cy="399" r="3"/>
  </g>
  <rect x="24" y="224" width="232" height="212" rx="18"
        fill="none" stroke="{theme.border}"/>
  {number_badge(40, 240, "02", theme)}

  <rect x="274" y="24" width="422" height="412" rx="20"
        fill="{theme.surface}"/>
  <image x="274" y="24" width="422" height="412"
         preserveAspectRatio="xMidYMid slice" href="{video_uri}"
         clip-path="url(#robot-clip)"/>
  <rect x="274" y="24" width="422" height="412"
        fill="url(#robot-shade)" clip-path="url(#robot-clip)"/>
  <path d="M298 {scan_y:.1f}H672" stroke="{theme.accent}"
        stroke-opacity="0.28" stroke-width="1"/>
  <path d="M302 52h-16v16 M668 52h16v16 M302 408h-16v-16 M668 408h16v-16"
        fill="none" stroke="{theme.ink}" stroke-opacity="0.52" stroke-width="1.4"/>
  <rect x="274" y="24" width="422" height="412" rx="20"
        fill="none" stroke="{theme.border}"/>
  {number_badge(290, 40, "03", theme)}

  <path d="M130 195V236 C130 278 196 318 255 344 H306 C414 344 550 344 658 344"
        fill="none" stroke="{theme.accent}" stroke-opacity="0.48"
        stroke-width="1.5" stroke-dasharray="4 7"/>
  <circle cx="130" cy="195" r="4" fill="{theme.accent}"/>
  <circle cx="255" cy="344" r="4" fill="{theme.accent}"/>
  <circle cx="658" cy="344" r="4" fill="{theme.accent}"/>
  <circle cx="{pulse_x:.1f}" cy="{pulse_y:.1f}" r="16" fill="url(#pulse)"/>
  <circle cx="{pulse_x:.1f}" cy="{pulse_y:.1f}" r="3.5" fill="{theme.accent}"/>
</svg>
"""


def render_variant(
    renderer: str,
    magick: str,
    temp: Path,
    name: str,
    svg_factory,
    theme: Theme,
    portrait: Path,
    study_frames: tuple[Path, Path, Path],
    video_frames: list[Path],
    webp_output: Path,
    poster_output: Path,
) -> None:
    variant_dir = temp / name
    variant_dir.mkdir()
    rendered_frames: list[Path] = []

    for frame_index, video_frame in enumerate(video_frames):
        svg_path = variant_dir / f"frame-{frame_index:03d}.svg"
        png_path = variant_dir / f"frame-{frame_index:03d}.png"
        svg_path.write_text(
            svg_factory(theme, portrait, study_frames, video_frame, frame_index),
            encoding="utf-8",
        )
        subprocess.run(
            [renderer, "--output", str(png_path), str(svg_path)],
            check=True,
        )
        rendered_frames.append(png_path)

    poster_svg = variant_dir / "poster.svg"
    poster_svg.write_text(
        svg_factory(
            theme,
            portrait,
            study_frames,
            video_frames[POSTER_SOURCE_FRAME],
            FRAME_COUNT - 1,
        ),
        encoding="utf-8",
    )
    subprocess.run(
        [renderer, "--output", str(poster_output), str(poster_svg)],
        check=True,
    )
    subprocess.run(
        [
            magick,
            *map(str, rendered_frames),
            "-set",
            "delay",
            str(FRAME_DELAY),
            "-loop",
            "1",
            "-quality",
            "82",
            "-define",
            "webp:method=6",
            "-define",
            "webp:thread-level=1",
            str(webp_output),
        ],
        check=True,
    )


def main() -> None:
    ffmpeg = shutil.which("ffmpeg")
    magick = shutil.which("magick")
    renderer = shutil.which("rsvg-convert")
    missing = [
        name
        for name, command in (
            ("ffmpeg", ffmpeg),
            ("ImageMagick", magick),
            ("librsvg", renderer),
        )
        if command is None
    ]
    if missing:
        raise SystemExit(f"Missing required tools: {', '.join(missing)}")

    ASSETS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-field-log-") as temp_dir:
        temp = Path(temp_dir)
        source_override = os.environ.get("README_SOURCE_DIR")
        sources = (
            load_local_sources(Path(source_override))
            if source_override
            else fetch_sources(temp / "sources")
        )
        video_frames = extract_video_frames(
            ffmpeg,
            sources["teleoperation.mp4"],
            temp / "video-frames",
        )
        study_frames = (
            video_frames[0],
            video_frames[POSTER_SOURCE_FRAME],
            video_frames[-1],
        )
        variants = (
            (
                "desktop-light",
                desktop_svg,
                LIGHT,
                ASSETS / "research-hero.webp",
                ASSETS / "research-hero.png",
            ),
            (
                "desktop-dark",
                desktop_svg,
                DARK,
                ASSETS / "research-hero-dark.webp",
                ASSETS / "research-hero-dark.png",
            ),
            (
                "mobile-light",
                mobile_svg,
                LIGHT,
                ASSETS / "research-hero-mobile.webp",
                ASSETS / "research-hero-mobile.png",
            ),
            (
                "mobile-dark",
                mobile_svg,
                DARK,
                ASSETS / "research-hero-mobile-dark.webp",
                ASSETS / "research-hero-mobile-dark.png",
            ),
        )
        for (
            name,
            svg_factory,
            theme,
            webp_output,
            poster_output,
        ) in variants:
            render_variant(
                renderer,
                magick,
                temp,
                name,
                svg_factory,
                theme,
                sources["portrait.jpg"],
                study_frames,
                video_frames,
                webp_output,
                poster_output,
            )

    print("Generated theme-aware research field-log assets.")


if __name__ == "__main__":
    main()
