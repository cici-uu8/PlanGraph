#!/usr/bin/env python3
"""Generate synthetic README assets for the public repository.

This script renders the logo, hero banner, and example screenshots used in
the repository README files. It reads sample Markdown outputs from
`examples/` and writes PNG assets into `assets/`.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
SAMPLES_DIR = ROOT / "examples"

BG = "#06141B"
PANEL = "#0B1F29"
PANEL_ALT = "#102A36"
TEXT = "#E8F1F4"
MUTED = "#9FB5BF"
TEAL = "#14B8A6"
TEAL_DARK = "#0F766E"
AMBER = "#F59E0B"
RED = "#F97316"
GRID = "#173543"
WHITE = "#FFFFFF"

FONT_SANS = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_SANS, size=size)


def cjk_font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_CJK, size=size)


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 24, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font_obj: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    if " " not in text:
        current = ""
        lines: list[str] = []
        for char in text:
            probe = current + char
            if draw.textlength(probe, font=font_obj) <= max_width or not current:
                current = probe
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        probe = word if not current else current + " " + word
        if draw.textlength(probe, font=font_obj) <= max_width or not current:
            current = probe
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def write_multiline(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, *, fill: str, font_obj: ImageFont.FreeTypeFont, max_width: int, line_gap: int = 10) -> int:
    x, y = xy
    lines: list[str] = []
    for paragraph in text.splitlines():
        if not paragraph:
            lines.append("")
            continue
        lines.extend(wrap_text(draw, paragraph, font_obj, max_width))
    line_height = font_obj.size + line_gap
    for idx, line in enumerate(lines):
        draw.text((x, y + idx * line_height), line, font=font_obj, fill=fill)
    return y + max(1, len(lines)) * line_height


def draw_badge(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fill: str, text_fill: str = WHITE, *, bold: bool = True) -> int:
    use_cjk = any(ord(ch) > 127 for ch in text)
    f = cjk_font(24) if use_cjk else font(24, bold=bold)
    padding_x = 18
    padding_y = 10
    w = int(draw.textlength(text, font=f)) + padding_x * 2
    h = 24 + padding_y * 2
    rounded(draw, (x, y, x + w, y + h), fill=fill, radius=20)
    draw.text((x + padding_x, y + padding_y - 2), text, font=f, fill=text_fill)
    return w


def card_title(draw: ImageDraw.ImageDraw, x: int, y: int, text: str) -> int:
    draw.text((x, y), text, font=font(26, bold=True), fill=WHITE)
    return y + 42


def generate_logo() -> None:
    img = Image.new("RGBA", (512, 512), BG)
    draw = ImageDraw.Draw(img)
    rounded(draw, (48, 48, 464, 464), fill=PANEL, radius=72, outline=TEAL_DARK, width=3)
    rounded(draw, (104, 92, 408, 180), fill=TEAL_DARK, radius=34)
    draw.text((136, 114), "PLAN", font=font(56, bold=True), fill=WHITE)
    rounded(draw, (104, 206, 408, 294), fill=PANEL_ALT, radius=34, outline=GRID, width=2)
    draw.text((132, 228), "REGISTRY", font=font(46, bold=True), fill=TEXT)
    rounded(draw, (104, 320, 248, 388), fill=AMBER, radius=24)
    draw.text((132, 337), "INIT", font=font(32, bold=True), fill=BG)
    rounded(draw, (264, 320, 408, 388), fill=TEAL, radius=24)
    draw.text((292, 337), "AUTO", font=font(32, bold=True), fill=BG)
    draw.line((256, 180, 256, 320), fill=TEAL, width=6)
    draw.polygon([(256, 320), (240, 292), (272, 292)], fill=TEAL)
    img.save(ASSETS_DIR / "logo.png")


def generate_banner() -> None:
    img = Image.new("RGBA", (1600, 900), BG)
    draw = ImageDraw.Draw(img)
    rounded(draw, (48, 48, 1552, 852), fill=PANEL, radius=40, outline=GRID, width=2)

    draw_badge(draw, 92, 88, "MIT", TEAL_DARK)
    draw_badge(draw, 208, 88, "Codex Plugin", PANEL_ALT)
    draw_badge(draw, 418, 88, "English / 简体中文", PANEL_ALT, bold=False)

    draw.text((92, 168), "Plan Governance", font=font(88, bold=True), fill=WHITE)
    write_multiline(
        draw,
        (92, 286),
        "Keep project plan docs current, visible, and governed across brownfield repos.",
        fill=TEXT,
        font_obj=font(34),
        max_width=720,
        line_gap=14,
    )

    draw.text((92, 430), "Why this exists", font=font(30, bold=True), fill=WHITE)
    write_multiline(
        draw,
        (92, 478),
        "Claude wrote a new execution plan. Codex did not confirm the current workstream and followed an older plan instead. "
        "This skill makes the current plan explicit, tracks replacements, and keeps the lifecycle visible inside the repo.",
        fill=MUTED,
        font_obj=font(26),
        max_width=720,
        line_gap=12,
    )

    rounded(draw, (900, 126, 1468, 780), fill=PANEL_ALT, radius=28, outline=GRID, width=2)
    draw.text((940, 168), "What you get", font=font(30, bold=True), fill=WHITE)
    items = [
        ("Read-only adoption analysis", "Identify likely plan docs before governance writes anything."),
        ("Canonical plan registry", "Track current, historical, superseded, and quarantined docs."),
        ("Autonomous upkeep", "Register, refresh, close, and lint as plans change."),
        ("Managed AGENTS block", "Keep agent behavior aligned after governance is enabled."),
    ]
    y = 226
    for title, desc in items:
        draw.ellipse((940, y + 10, 960, y + 30), fill=TEAL)
        draw.text((978, y), title, font=font(24, bold=True), fill=TEXT)
        y = write_multiline(draw, (978, y + 34), desc, fill=MUTED, font_obj=font(20), max_width=430, line_gap=8) + 18

    draw.text((92, 744), "Two entry phrases. Ongoing maintenance after enablement.", font=font(24, bold=True), fill=AMBER)
    img.save(ASSETS_DIR / "hero-banner.png")


def read_text(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def render_report(lines: list[str], title: str, subtitle: str, out_name: str) -> None:
    width, height = 1600, 1040
    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)
    rounded(draw, (40, 40, width - 40, height - 40), fill=PANEL, radius=36, outline=GRID, width=2)
    draw.text((84, 82), title, font=font(54, bold=True), fill=WHITE)
    draw.text((84, 150), subtitle, font=font(24), fill=MUTED)

    content_box = (84, 208, width - 84, height - 84)
    rounded(draw, content_box, fill=PANEL_ALT, radius=24, outline=GRID, width=2)
    x = content_box[0] + 28
    y = content_box[1] + 28
    max_width = content_box[2] - content_box[0] - 56

    mono = font(20)
    heading = font(22, bold=True)
    table_font = font(18)

    for raw in lines[:38]:
        line = raw.rstrip()
        if not line:
            y += 16
            continue
        if line.startswith("#"):
            level_text = line.lstrip("# ").strip()
            draw.text((x, y), level_text, font=heading, fill=WHITE)
            y += 34
            continue
        if line.startswith("|"):
            color = TEAL if "---" not in line else GRID
            current_font = table_font
        elif line.startswith("- ") or line[:2].isdigit() and line[1:3] == ". ":
            color = TEXT
            current_font = mono
        elif line.startswith("`") or line.startswith('"'):
            color = TEAL
            current_font = mono
        else:
            color = TEXT
            current_font = mono
        y = write_multiline(draw, (x, y), line, fill=color, font_obj=current_font, max_width=max_width, line_gap=6) + 4
        if y > content_box[3] - 50:
            break

    img.save(ASSETS_DIR / out_name)


def parse_markdown_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if set(stripped.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def render_registry_table(lines: list[str]) -> None:
    width, height = 1600, 960
    img = Image.new("RGBA", (width, height), BG)
    draw = ImageDraw.Draw(img)
    rounded(draw, (40, 40, width - 40, height - 40), fill=PANEL, radius=36, outline=GRID, width=2)
    draw.text((84, 82), "Plan registry", font=font(54, bold=True), fill=WHITE)
    draw.text((84, 150), "Canonical registry for active, historical, and superseded plan docs", font=font(24), fill=MUTED)

    header_y = 248
    columns = [
        ("Plan ID", 132),
        ("Role", 380),
        ("Path", 580),
        ("Lifecycle", 1088),
        ("Source", 1300),
    ]
    rows = parse_markdown_table(lines)[1:]
    normalized = []
    for row in rows:
        normalized.append([
            row[0],
            row[3],
            row[2],
            row[5],
            row[8],
        ])

    rounded(draw, (84, 210, width - 84, 850), fill=PANEL_ALT, radius=24, outline=GRID, width=2)
    rounded(draw, (104, header_y, width - 104, header_y + 54), fill=TEAL_DARK, radius=16)
    for label, x in columns:
        draw.text((x, header_y + 14), label, font=font(22, bold=True), fill=WHITE)

    row_y = header_y + 82
    row_height = 92
    for index, row in enumerate(normalized):
        bg = PANEL if index % 2 == 0 else PANEL_ALT
        rounded(draw, (104, row_y - 10, width - 104, row_y + row_height - 14), fill=bg, radius=16, outline=GRID, width=1)
        draw.text((84, 0), "", font=font(1), fill=WHITE)
        draw.text((columns[0][1], row_y), row[0], font=font(20, bold=True), fill=TEXT)
        draw.text((columns[1][1], row_y), row[1], font=font(20), fill=TEXT)
        write_multiline(draw, (columns[2][1], row_y), row[2], fill=TEXT, font_obj=font(18), max_width=440, line_gap=4)
        draw.text((columns[3][1], row_y), row[3], font=font(20), fill=AMBER if row[3] == "active" else TEXT)
        draw.text((columns[4][1], row_y), row[4], font=font(18), fill=TEAL)
        row_y += row_height

    out = ASSETS_DIR / "screenshot-registry.png"
    img.save(out)
    img.save(ASSETS_DIR / "screenshot-registry-v2.png")


def generate_report_assets() -> None:
    render_report(
        read_text(SAMPLES_DIR / "plan_adoption_report.sample.md"),
        "Adoption report",
        "Read-only bootstrap analysis for brownfield repositories",
        "screenshot-adoption-report.png",
    )
    render_registry_table(read_text(SAMPLES_DIR / "plan_registry.sample.md"))
    render_report(
        read_text(SAMPLES_DIR / "plan_timeline_report.sample.md"),
        "Timeline report",
        "Derived lifecycle view after governance is enabled",
        "screenshot-timeline.png",
    )


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    generate_logo()
    generate_banner()
    generate_report_assets()
    print("Generated README assets in", ASSETS_DIR)


if __name__ == "__main__":
    main()
