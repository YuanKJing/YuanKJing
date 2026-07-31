#!/usr/bin/env python3
"""Generate the editorial research-map animations used by README.md."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
FRAME_COUNT = 84
FRAME_DELAY = 9

FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Avenir Next.ttc"),
    Path("/System/Library/Fonts/HelveticaNeue.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
)
FONT = next((candidate for candidate in FONT_CANDIDATES if candidate.exists()), None)

PAPER = "#F3EFE6"
PAPER_HIGHLIGHT = "#FAF7F0"
INK = "#153244"
SECONDARY = "#49636E"
HAIRLINE = "#AAB8B4"
CYAN = "#5D9094"
CYAN_LIGHT = "#A9C5C2"
CYAN_WASH = "#DDE8E2"
AMBER = "#C9824A"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(start: float, end: float, value: float) -> float:
    if start == end:
        return float(value >= end)
    position = clamp((value - start) / (end - start))
    return position * position * (3.0 - 2.0 * position)


def phase(value: float, start: float, end: float) -> float:
    return clamp((value - start) / (end - start))


def bell(value: float) -> float:
    return math.sin(math.pi * clamp(value)) ** 2


def cubic_point(
    start: tuple[float, float],
    control_one: tuple[float, float],
    control_two: tuple[float, float],
    end: tuple[float, float],
    progress: float,
) -> tuple[float, float]:
    progress = clamp(progress)
    inverse = 1.0 - progress
    x = (
        inverse**3 * start[0]
        + 3.0 * inverse**2 * progress * control_one[0]
        + 3.0 * inverse * progress**2 * control_two[0]
        + progress**3 * end[0]
    )
    y = (
        inverse**3 * start[1]
        + 3.0 * inverse**2 * progress * control_one[1]
        + 3.0 * inverse * progress**2 * control_two[1]
        + progress**3 * end[1]
    )
    return x, y


def latent_nodes(center_x: float, center_y: float, scale: float) -> str:
    nodes = (
        (-48, -21, 3.2),
        (-30, 20, 2.4),
        (-12, -34, 2.7),
        (2, 8, 3.5),
        (21, -13, 2.6),
        (36, 27, 3.0),
        (50, -29, 2.2),
        (59, 8, 2.8),
        (-57, 12, 2.1),
    )
    markup = []
    for index, (offset_x, offset_y, radius) in enumerate(nodes):
        color = CYAN if index in {0, 3, 5, 7} else INK
        opacity = 0.44 if index in {0, 3, 5, 7} else 0.22
        markup.append(
            f'<circle cx="{center_x + offset_x * scale:.2f}" '
            f'cy="{center_y + offset_y * scale:.2f}" '
            f'r="{radius * scale:.2f}" fill="{color}" '
            f'fill-opacity="{opacity:.2f}"/>'
        )
    return "\n".join(markup)


def packet_markup(
    start: tuple[float, float],
    control_one: tuple[float, float],
    control_two: tuple[float, float],
    end: tuple[float, float],
    encode_progress: float,
    scale: float,
) -> str:
    packets = []
    for index in range(3):
        local = clamp((encode_progress - index * 0.17) / 0.66)
        opacity = bell(local)
        x, y = cubic_point(start, control_one, control_two, end, local)
        trail_x, trail_y = cubic_point(
            start, control_one, control_two, end, max(0.0, local - 0.07)
        )
        packets.append(
            f"""
            <circle cx="{trail_x:.2f}" cy="{trail_y:.2f}" r="{2.2 * scale:.2f}"
                    fill="{CYAN}" fill-opacity="{0.18 * opacity:.3f}"/>
            <circle cx="{x:.2f}" cy="{y:.2f}" r="{3.4 * scale:.2f}"
                    fill="{CYAN}" fill-opacity="{0.78 * opacity:.3f}"/>
            """
        )
    return "".join(packets)


def desktop_svg(frame: int) -> str:
    width, height = 1200, 360
    time = frame / (FRAME_COUNT - 1)

    observe_progress = phase(time, 0.00, 0.20)
    observe_opacity = bell(observe_progress)
    scan_y = 132.0 + 66.0 * smoothstep(0.0, 1.0, observe_progress)

    encode_progress = phase(time, 0.20, 0.39)
    imagine_progress = phase(time, 0.38, 0.64)
    imagine_motion = bell(imagine_progress)
    ring_rotation = 8.0 * imagine_motion
    ring_scale = 1.0 + 0.025 * imagine_motion

    act_progress = phase(time, 0.63, 0.82)
    act_opacity = bell(act_progress)
    feedback_progress = phase(time, 0.81, 1.00)
    feedback_opacity = bell(feedback_progress)
    hand_shift = -3.0 * smoothstep(0.38, 0.92, act_progress)
    hand_shift *= 1.0 - smoothstep(0.25, 0.95, feedback_progress)

    sensor_left, sensor_top = 590.0, 126.0
    sensor_right, sensor_mid = 710.0, 165.0
    model_x, model_y = 842.0, 166.0

    gripper = (1081.0 + hand_shift, 105.0)
    action_start = (908.0, 166.0)
    action_control_one = (962.0, 146.0)
    action_control_two = (1018.0, 112.0)
    token_x, token_y = cubic_point(
        action_start,
        action_control_one,
        action_control_two,
        gripper,
        smoothstep(0.0, 1.0, act_progress),
    )

    feedback_start = (1090.0, 258.0)
    feedback_end = (650.0, 257.0)
    feedback_x, feedback_y = cubic_point(
        feedback_start,
        (990.0, 310.0),
        (748.0, 310.0),
        feedback_end,
        smoothstep(0.0, 1.0, feedback_progress),
    )

    packets = packet_markup(
        (sensor_right, sensor_mid),
        (750.0, 163.0),
        (780.0, 165.0),
        (807.0, 166.0),
        encode_progress,
        1.0,
    )

    trajectory_opacity = 0.20 + 0.52 * max(imagine_motion, act_opacity)
    active_dash = 88.0 * (1.0 - smoothstep(0.0, 1.0, imagine_progress))
    joint_one = 0.25 + 0.65 * bell(clamp((act_progress - 0.05) / 0.55))
    joint_two = 0.25 + 0.65 * bell(clamp((act_progress - 0.18) / 0.55))
    joint_three = 0.25 + 0.65 * bell(clamp((act_progress - 0.30) / 0.55))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="paper" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{PAPER_HIGHLIGHT}"/>
      <stop offset="58%" stop-color="{PAPER}"/>
      <stop offset="100%" stop-color="#ECE9DF"/>
    </linearGradient>
    <radialGradient id="wash" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{CYAN_WASH}" stop-opacity="0.90"/>
      <stop offset="100%" stop-color="{CYAN_WASH}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect x="1" y="1" width="1198" height="358" rx="20"
        fill="url(#paper)" stroke="{HAIRLINE}" stroke-opacity="0.48"/>
  <circle cx="842" cy="166" r="128" fill="url(#wash)"/>

  <g stroke="{INK}" stroke-opacity="0.035" stroke-width="1">
    <path d="M548 72H1150 M548 126H1150 M548 180H1150 M548 234H1150 M548 288H1150"/>
  </g>
  <path d="M516 48V312" stroke="{HAIRLINE}" stroke-opacity="0.38"/>

  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="64" y="66" fill="{SECONDARY}" font-size="13" font-weight="600"
          letter-spacing="2.2">RESEARCH MAP · EMBODIED INTELLIGENCE</text>
    <text x="64" y="132" fill="{INK}" font-family="New York, Georgia, serif"
          font-size="42" font-weight="500">World models for</text>
    <text x="64" y="180" fill="{INK}" font-family="New York, Georgia, serif"
          font-size="42" font-weight="500">embodied intelligence</text>
    <text x="65" y="226" fill="{SECONDARY}" font-size="16">
      Learning systems that observe, imagine, and act.
    </text>
    <text x="65" y="294" fill="{SECONDARY}" font-size="11.5" font-weight="600"
          letter-spacing="1.15">PERCEPTION  /  LATENT DYNAMICS  /  ROBOT CONTROL</text>
    <text x="1128" y="61" text-anchor="end" fill="{SECONDARY}" font-size="11"
          letter-spacing="1.8">FIG. 01</text>
  </g>

  <!-- Observe -->
  <g>
    <rect x="{sensor_left}" y="{sensor_top}" width="120" height="78" rx="10"
          fill="{PAPER_HIGHLIGHT}" fill-opacity="0.58"
          stroke="{INK}" stroke-opacity="0.34"/>
    <path d="M602 182 C620 169 635 173 650 159 C664 146 682 151 698 139"
          fill="none" stroke="{HAIRLINE}" stroke-opacity="0.70" stroke-width="1.2"/>
    <path d="M602 186H698" stroke="{HAIRLINE}" stroke-opacity="0.50"/>
    <circle cx="620" cy="169" r="3.2" fill="{CYAN}"
            fill-opacity="{0.28 + 0.58 * observe_opacity:.3f}"/>
    <circle cx="652" cy="158" r="3.2" fill="{CYAN}"
            fill-opacity="{0.28 + 0.50 * observe_opacity:.3f}"/>
    <circle cx="681" cy="151" r="3.2" fill="{CYAN}"
            fill-opacity="{0.28 + 0.42 * observe_opacity:.3f}"/>
    <path d="M600 {scan_y:.2f}H700" stroke="{CYAN}" stroke-width="1.2"
          stroke-opacity="{0.52 * observe_opacity:.3f}"/>
  </g>
  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="590" y="115" fill="{SECONDARY}" font-size="11" letter-spacing="1.3">01  OBSERVE</text>
    <text x="650" y="222" text-anchor="middle" fill="{INK}" font-size="12" font-weight="600">SENSOR STATE</text>
  </g>

  <!-- Encode -->
  <path d="M710 165 C750 163 780 165 807 166" fill="none"
        stroke="{HAIRLINE}" stroke-opacity="0.62" stroke-width="1.2"
        stroke-dasharray="4 6"/>
  {packets}

  <!-- Imagine -->
  <g transform="translate({model_x} {model_y}) rotate({ring_rotation:.3f}) scale({ring_scale:.4f}) translate({-model_x} {-model_y})">
    <ellipse cx="{model_x}" cy="{model_y}" rx="72" ry="56" fill="none"
             stroke="{CYAN}" stroke-opacity="0.66" stroke-width="1.4"/>
    <ellipse cx="{model_x}" cy="{model_y}" rx="44" ry="33" fill="none"
             stroke="{INK}" stroke-opacity="0.32" stroke-width="1.2"
             stroke-dasharray="6 7"/>
    <path d="M776 178 C800 126 862 116 907 154 C874 205 818 219 776 178Z"
          fill="{CYAN_WASH}" fill-opacity="0.30"
          stroke="{HAIRLINE}" stroke-opacity="0.48"/>
    {latent_nodes(model_x, model_y, 1.0)}
  </g>
  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="842" y="86" text-anchor="middle" fill="{SECONDARY}" font-size="11"
          letter-spacing="1.3">02  IMAGINE</text>
    <text x="842" y="244" text-anchor="middle" fill="{INK}" font-size="12"
          font-weight="600">WORLD MODEL</text>
    <text x="842" y="260" text-anchor="middle" fill="{SECONDARY}" font-size="10.5">
      latent dynamics
    </text>
  </g>

  <!-- Candidate action trajectories -->
  <path d="M908 166 C962 132 1026 92 {gripper[0]:.2f} {gripper[1]:.2f}"
        fill="none" stroke="{INK}" stroke-opacity="0.11" stroke-width="1.2"/>
  <path d="M908 166 C974 173 1030 145 {gripper[0]:.2f} {gripper[1]:.2f}"
        fill="none" stroke="{INK}" stroke-opacity="0.08" stroke-width="1.2"/>
  <path d="M908 166 C962 146 1018 112 {gripper[0]:.2f} {gripper[1]:.2f}"
        fill="none" stroke="{AMBER}" stroke-opacity="{trajectory_opacity:.3f}"
        stroke-width="1.7" stroke-dasharray="7 6" stroke-dashoffset="{active_dash:.2f}"/>
  <circle cx="{token_x:.2f}" cy="{token_y:.2f}" r="4.6" fill="{AMBER}"
          fill-opacity="{0.92 * act_opacity:.3f}"/>

  <!-- Act: abstract robot arm -->
  <g fill="none" stroke="{INK}" stroke-linecap="round" stroke-linejoin="round">
    <path d="M1090 252 L1067 214 L1091 162 L1056 123 L{gripper[0]:.2f} {gripper[1]:.2f}"
          stroke-width="2.2" stroke-opacity="0.70"/>
    <path d="M1073 252H1107 M1078 258H1102" stroke-width="2" stroke-opacity="0.55"/>
    <path d="M{gripper[0]:.2f} {gripper[1]:.2f} l18 -12 M{gripper[0]:.2f} {gripper[1]:.2f} l16 13"
          stroke-width="2" stroke-opacity="0.75"/>
    <rect x="1100" y="86" width="22" height="22" rx="3"
          stroke="{AMBER}" stroke-opacity="0.62" stroke-width="1.4"/>
  </g>
  <g>
    <circle cx="1067" cy="214" r="7" fill="{PAPER}" stroke="{INK}"
            stroke-opacity="{joint_one:.3f}" stroke-width="2"/>
    <circle cx="1091" cy="162" r="7" fill="{PAPER}" stroke="{INK}"
            stroke-opacity="{joint_two:.3f}" stroke-width="2"/>
    <circle cx="1056" cy="123" r="6" fill="{PAPER}" stroke="{INK}"
            stroke-opacity="{joint_three:.3f}" stroke-width="2"/>
    <circle cx="{gripper[0]:.2f}" cy="{gripper[1]:.2f}" r="4.5"
            fill="{AMBER}" fill-opacity="{0.32 + 0.48 * act_opacity:.3f}"/>
  </g>
  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="1032" y="86" fill="{SECONDARY}" font-size="11" letter-spacing="1.3">03  ACT</text>
    <text x="1080" y="282" text-anchor="middle" fill="{INK}" font-size="12"
          font-weight="600">ROBOT CONTROL</text>
  </g>

  <!-- Feedback -->
  <path d="M1090 258 C990 310 748 310 650 257" fill="none"
        stroke="{HAIRLINE}" stroke-opacity="0.62" stroke-width="1.2"/>
  <circle cx="{feedback_x:.2f}" cy="{feedback_y:.2f}" r="3.8" fill="{CYAN}"
          fill-opacity="{0.86 * feedback_opacity:.3f}"/>
  <text x="869" y="315" text-anchor="middle" fill="{SECONDARY}"
        font-family="Avenir Next, Helvetica Neue, sans-serif" font-size="10.5"
        letter-spacing="0.8">closed-loop adaptation</text>
</svg>
"""


def mobile_svg(frame: int) -> str:
    width, height = 720, 360
    time = frame / (FRAME_COUNT - 1)

    observe_progress = phase(time, 0.00, 0.20)
    observe_opacity = bell(observe_progress)
    scan_y = 183.0 + 49.0 * smoothstep(0.0, 1.0, observe_progress)
    encode_progress = phase(time, 0.20, 0.39)
    imagine_progress = phase(time, 0.38, 0.64)
    imagine_motion = bell(imagine_progress)
    act_progress = phase(time, 0.63, 0.82)
    act_opacity = bell(act_progress)
    feedback_progress = phase(time, 0.81, 1.00)
    feedback_opacity = bell(feedback_progress)
    hand_shift = -2.5 * smoothstep(0.38, 0.92, act_progress)
    hand_shift *= 1.0 - smoothstep(0.25, 0.95, feedback_progress)

    model_x, model_y = 360.0, 210.0
    gripper = (627.0 + hand_shift, 169.0)
    token_x, token_y = cubic_point(
        (417.0, 210.0),
        (480.0, 195.0),
        (555.0, 168.0),
        gripper,
        smoothstep(0.0, 1.0, act_progress),
    )
    feedback_x, feedback_y = cubic_point(
        (636.0, 283.0),
        (520.0, 330.0),
        (220.0, 330.0),
        (105.0, 282.0),
        smoothstep(0.0, 1.0, feedback_progress),
    )
    packets = packet_markup(
        (224.0, 210.0),
        (270.0, 207.0),
        (298.0, 210.0),
        (310.0, 210.0),
        encode_progress,
        0.9,
    )
    trajectory_opacity = 0.20 + 0.52 * max(imagine_motion, act_opacity)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="paper" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{PAPER_HIGHLIGHT}"/>
      <stop offset="65%" stop-color="{PAPER}"/>
      <stop offset="100%" stop-color="#ECE9DF"/>
    </linearGradient>
    <radialGradient id="wash" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{CYAN_WASH}" stop-opacity="0.90"/>
      <stop offset="100%" stop-color="{CYAN_WASH}" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect x="1" y="1" width="718" height="358" rx="20"
        fill="url(#paper)" stroke="{HAIRLINE}" stroke-opacity="0.48"/>
  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="40" y="47" fill="{SECONDARY}" font-size="11.5" font-weight="600"
          letter-spacing="1.8">RESEARCH MAP · EMBODIED INTELLIGENCE</text>
    <text x="40" y="91" fill="{INK}" font-family="New York, Georgia, serif"
          font-size="31" font-weight="500">Observe, imagine, and act.</text>
    <text x="40" y="119" fill="{SECONDARY}" font-size="14">
      World models for embodied intelligence
    </text>
    <text x="680" y="47" text-anchor="end" fill="{SECONDARY}" font-size="10"
          letter-spacing="1.4">FIG. 01</text>
  </g>
  <path d="M40 141H680" stroke="{HAIRLINE}" stroke-opacity="0.48"/>

  <circle cx="{model_x}" cy="{model_y}" r="91" fill="url(#wash)"/>

  <!-- Observe -->
  <rect x="104" y="178" width="120" height="66" rx="10"
        fill="{PAPER_HIGHLIGHT}" fill-opacity="0.60"
        stroke="{INK}" stroke-opacity="0.34"/>
  <path d="M115 229 C132 216 151 220 166 204 C183 189 199 196 214 186"
        fill="none" stroke="{HAIRLINE}" stroke-opacity="0.72"/>
  <circle cx="138" cy="215" r="3" fill="{CYAN}"
          fill-opacity="{0.28 + 0.58 * observe_opacity:.3f}"/>
  <circle cx="169" cy="202" r="3" fill="{CYAN}"
          fill-opacity="{0.28 + 0.50 * observe_opacity:.3f}"/>
  <circle cx="199" cy="195" r="3" fill="{CYAN}"
          fill-opacity="{0.28 + 0.42 * observe_opacity:.3f}"/>
  <path d="M113 {scan_y:.2f}H215" stroke="{CYAN}" stroke-width="1.2"
        stroke-opacity="{0.52 * observe_opacity:.3f}"/>

  <path d="M224 210 C270 207 298 210 310 210" fill="none"
        stroke="{HAIRLINE}" stroke-opacity="0.62" stroke-dasharray="4 6"/>
  {packets}

  <!-- Imagine -->
  <g transform="translate({model_x} {model_y}) rotate({7.0 * imagine_motion:.3f}) scale({1.0 + 0.025 * imagine_motion:.4f}) translate({-model_x} {-model_y})">
    <ellipse cx="{model_x}" cy="{model_y}" rx="55" ry="45" fill="none"
             stroke="{CYAN}" stroke-opacity="0.68" stroke-width="1.4"/>
    <ellipse cx="{model_x}" cy="{model_y}" rx="34" ry="27" fill="none"
             stroke="{INK}" stroke-opacity="0.34" stroke-dasharray="5 6"/>
    {latent_nodes(model_x, model_y, 0.76)}
  </g>

  <!-- Action path and arm -->
  <path d="M417 210 C480 195 555 168 {gripper[0]:.2f} {gripper[1]:.2f}"
        fill="none" stroke="{AMBER}" stroke-opacity="{trajectory_opacity:.3f}"
        stroke-width="1.7" stroke-dasharray="7 6"/>
  <path d="M417 210 C490 226 557 205 {gripper[0]:.2f} {gripper[1]:.2f}"
        fill="none" stroke="{INK}" stroke-opacity="0.09"/>
  <circle cx="{token_x:.2f}" cy="{token_y:.2f}" r="4.2" fill="{AMBER}"
          fill-opacity="{0.92 * act_opacity:.3f}"/>

  <g fill="none" stroke="{INK}" stroke-linecap="round" stroke-linejoin="round">
    <path d="M636 283 L613 252 L640 215 L608 187 L{gripper[0]:.2f} {gripper[1]:.2f}"
          stroke-width="2.2" stroke-opacity="0.70"/>
    <path d="M620 283H652 M625 289H647" stroke-width="2" stroke-opacity="0.55"/>
    <path d="M{gripper[0]:.2f} {gripper[1]:.2f} l15 -10 M{gripper[0]:.2f} {gripper[1]:.2f} l14 11"
          stroke-width="2" stroke-opacity="0.76"/>
    <rect x="645" y="151" width="19" height="19" rx="3"
          stroke="{AMBER}" stroke-opacity="0.62" stroke-width="1.4"/>
  </g>
  <g fill="{PAPER}" stroke="{INK}" stroke-width="2">
    <circle cx="613" cy="252" r="6"/>
    <circle cx="640" cy="215" r="6"/>
    <circle cx="608" cy="187" r="5.5"/>
  </g>
  <circle cx="{gripper[0]:.2f}" cy="{gripper[1]:.2f}" r="4.2" fill="{AMBER}"
          fill-opacity="{0.32 + 0.48 * act_opacity:.3f}"/>

  <!-- Labels and feedback -->
  <g font-family="Avenir Next, Helvetica Neue, sans-serif">
    <text x="164" y="270" text-anchor="middle" fill="{INK}" font-size="14"
          font-weight="600">01 · Observe</text>
    <text x="360" y="281" text-anchor="middle" fill="{INK}" font-size="14"
          font-weight="600">02 · Imagine</text>
    <text x="620" y="315" text-anchor="middle" fill="{INK}" font-size="14"
          font-weight="600">03 · Act</text>
  </g>
  <path d="M636 283 C520 330 220 330 105 282" fill="none"
        stroke="{HAIRLINE}" stroke-opacity="0.62" stroke-width="1.2"/>
  <circle cx="{feedback_x:.2f}" cy="{feedback_y:.2f}" r="3.6" fill="{CYAN}"
          fill-opacity="{0.86 * feedback_opacity:.3f}"/>
</svg>
"""


def render_animation(
    magick: str,
    renderer: str,
    temp: Path,
    name: str,
    svg_factory,
    output: Path,
    poster: Path,
) -> None:
    frame_dir = temp / name
    frame_dir.mkdir()
    png_frames: list[Path] = []

    for frame in range(FRAME_COUNT):
        svg_path = frame_dir / f"frame-{frame:03d}.svg"
        png_path = frame_dir / f"frame-{frame:03d}.png"
        svg_path.write_text(svg_factory(frame), encoding="utf-8")
        subprocess.run(
            [renderer, "--output", str(png_path), str(svg_path)],
            check=True,
        )
        png_frames.append(png_path)

    shutil.copyfile(png_frames[0], poster)
    subprocess.run(
        [
            magick,
            *map(str, png_frames),
            "-set",
            "delay",
            str(FRAME_DELAY),
            "-loop",
            "0",
            "-dither",
            "None",
            "-colors",
            "88",
            "-layers",
            "Optimize",
            str(output),
        ],
        check=True,
    )
    optimized = frame_dir / f"{name}-optimized.gif"
    subprocess.run(
        [
            magick,
            str(output),
            "-coalesce",
            "-fuzz",
            "2%",
            "-layers",
            "Optimize",
            "-layers",
            "OptimizeTransparency",
            str(optimized),
        ],
        check=True,
    )
    shutil.move(optimized, output)


def main() -> None:
    magick = shutil.which("magick")
    renderer = shutil.which("rsvg-convert")
    if magick is None:
        raise SystemExit("ImageMagick is required: install it and rerun this script.")
    if renderer is None:
        raise SystemExit("librsvg is required: install rsvg-convert and rerun.")
    if FONT is None:
        raise SystemExit(
            "No supported font was found. Install Avenir Next or DejaVu Sans."
        )

    ASSETS.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="research-map-") as temp_dir:
        temp = Path(temp_dir)
        render_animation(
            magick,
            renderer,
            temp,
            "desktop",
            desktop_svg,
            ASSETS / "research-hero.gif",
            ASSETS / "research-hero.png",
        )
        render_animation(
            magick,
            renderer,
            temp,
            "mobile",
            mobile_svg,
            ASSETS / "research-hero-mobile.gif",
            ASSETS / "research-hero-mobile.png",
        )

    print("Generated editorial research-map assets.")


if __name__ == "__main__":
    main()
