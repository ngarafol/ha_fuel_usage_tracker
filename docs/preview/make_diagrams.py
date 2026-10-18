#!/usr/bin/env python3
"""Generate the preview diagrams (monthly comparison + data flow) for the docs.

Reads the real exported HA sensor states from /tmp/fut_states.json and writes
two self-contained HTML pages next to this script:

    docs/preview/monthly-chart.html   -> docs/images/monthly-chart.png
    docs/preview/architecture.html    -> docs/images/architecture.png

Regenerate the state export first (throwaway pytest run), then:

    cd /Users/nix/git/ha_fuel_usage_tracker
    .venv/bin/python docs/preview/make_diagrams.py          # writes the two HTML pages
    CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    # --window-size must be LARGER than the page: Chrome's --screenshot then
    # captures a page-sized picture with blank space around it, which the last
    # step trims off. Undersizing the window silently crops the drawing.
    "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --disable-crash-reporter --run-all-compositor-stages-before-draw \
      --user-data-dir="$(mktemp -d)" --force-device-scale-factor=2 \
      --window-size=2100,1400 --virtual-time-budget=1500 \
      --screenshot=docs/images/architecture.png \
      "file://$PWD/docs/preview/architecture.html"
    "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --disable-crash-reporter --run-all-compositor-stages-before-draw \
      --user-data-dir="$(mktemp -d)" --force-device-scale-factor=2 \
      --window-size=2200,1700 --virtual-time-budget=1500 \
      --screenshot=docs/images/monthly-chart.png \
      "file://$PWD/docs/preview/monthly-chart.html"
    .venv/bin/python docs/preview/make_diagrams.py --crop     # trims the blank page area
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from custom_components.fuelusagetracker.data import FillUp, FuelUsage  # noqa: E402

STATES = Path("/tmp/fut_states.json")

INK = "#1c1c1e"
MUTED = "#6b7280"
GRID = "#e5e7eb"
BLUE = "#4f8ef7"
ORANGE = "#f59e0b"
GREEN = "#22a06b"

CHART_W, CHART_H = 960, 780


def load() -> dict:
    data = json.loads(STATES.read_text())
    sensors = {state["attributes"].get("key"): state for state in data["states"]}
    raw = list(reversed(sensors["last_fill"]["attributes"]["fillups"]))
    # Reuse the integration's own model: the previews must show exactly what the
    # sensors compute, so no second implementation of the maths lives here.
    usage = FuelUsage(fillups=[FillUp.from_dict(fill) for fill in raw])
    months = [month.as_dict() for month in usage.months()]
    fillups = [
        {**fill, "date": datetime.fromisoformat(str(fill["date"]).replace("Z", "+00:00"))}
        for fill in raw
    ]
    return {
        "title": data["title"],
        "sensors": sensors,
        "fillups": fillups,
        "usage": usage,
        "months": months,
    }


def hr(value: float, digits: int = 2) -> str:
    """Format a number the way the Croatian UI does: 1.234,56."""
    formatted = f"{value:,.{digits}f}"
    return formatted.replace(",", "\u00a0").replace(".", ",").replace("\u00a0", ".")


def esc(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def text(x: float, y: float, content: object, **kw) -> str:
    attrs = " ".join(f'{k.rstrip("_").replace("_", "-")}="{v}"' for k, v in kw.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {attrs}>{esc(content)}</text>'


def architecture_html(title: str) -> str:
    boxes = [
        ("Vozilo (config entry)\nnaziv · gorivo · motor · km", 40, 150, 190, 76, "#eef4ff", "#4f8ef7"),
        ("Servisi\nadd_fillup · update_fillup\ndelete_fillup · update_vehicle", 280, 150, 230, 76, "#fff7e6", ORANGE),
        ("Store po vozilu\n.storage/fuelusagetracker.<id>\nlitre · cijena · odometar · datum", 560, 150, 250, 76, "#eefaf3", GREEN),
        ("FuelUsage + koordinator\ntank-to-tank L/100km · mjesečno\n€/km · km · potrošnja", 560, 300, 250, 76, "#eefaf3", GREEN),
        ("19 senzora po vozilu\nukupno + ovaj mjesec", 280, 300, 230, 76, "#eef4ff", "#4f8ef7"),
        ("fuelusagetracker-card\nstatistika · unos · povijest", 40, 300, 190, 76, "#f7f0ff", "#8b5cf6"),
    ]
    svg = [
        f'<svg viewBox="0 0 900 560" width="900" height="560" xmlns="http://www.w3.org/2000/svg" '
        'font-family="system-ui, -apple-system, sans-serif">',
        '<defs><marker id="a" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
        '<path d="M0 0 L10 4 L0 8 z" fill="#9aa3af"/></marker></defs>',
        '<rect width="900" height="560" rx="14" fill="#fff"/>',
        text(40, 52, f"Fuel Usage Tracker — tok podataka ({title})", font_size="20",
             font_weight="600", fill=INK),
        text(40, 76, "sve lokalno u Home Assistantu, bez clouda i bez vanjske baze",
             font_size="13", fill=MUTED),
    ]
    for label, x, y, w, h, fill, stroke in boxes:
        svg.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="1.5"/>'
        )
        lines = label.split("\n")
        for line_index, line in enumerate(lines):
            svg.append(
                text(x + 14, y + 26 + line_index * 18, line,
                     font_size="14" if line_index == 0 else "12",
                     font_weight="600" if line_index == 0 else "400",
                     fill=INK if line_index == 0 else MUTED)
            )

    arrows = [
        (230, 188, 280, 188), (510, 188, 560, 188), (685, 226, 685, 300),
        (560, 338, 510, 338), (280, 338, 230, 338), (135, 300, 135, 226),
    ]
    for ax, ay, bx, by in arrows:
        svg.append(
            f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" stroke="#9aa3af" stroke-width="2" '
            'marker-end="url(#a)"/>'
        )
    svg.append(text(255, 180, "servis", font_size="11", fill=MUTED))
    svg.append(text(516, 180, "zapis", font_size="11", fill=MUTED))
    svg.append(text(694, 268, "računa", font_size="11", fill=MUTED))
    svg.append(text(516, 330, "objavljuje", font_size="11", fill=MUTED))
    svg.append(text(245, 330, "čita", font_size="11", fill=MUTED))
    svg.append(text(143, 268, "unos", font_size="11", fill=MUTED))

    # phase 2
    svg.append(
        '<rect x="280" y="440" width="530" height="80" rx="10" fill="#fbfbfd" stroke="#9aa3af" '
        'stroke-width="1.5" stroke-dasharray="6 5"/>'
    )
    svg.append(text(296, 470, "Faza 2 — OCR računa (nije implementirano)", font_size="14",
                    font_weight="600", fill=MUTED))
    svg.append(text(296, 492, "fotografija računa → OCR izvuče datum / iznos / litre → "
                              "isti add_fillup servis", font_size="12", fill=MUTED))
    svg.append('<path d="M280 480 L260 480 L260 230 L280 230" fill="none" stroke="#9aa3af" '
               'stroke-width="2" stroke-dasharray="6 5" marker-end="url(#a)"/>')
    svg.append("</svg>")
    return (
        "<!doctype html>\n<html lang=\"hr\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Fuel Usage Tracker — arhitektura</title>\n"
        "<style>html,body{margin:0;padding:0;background:#f4f5f7}</style>\n</head>\n<body>\n"
        + "\n".join(svg) + "\n</body>\n</html>\n"
    )


def monthly_chart_html(data: dict, months: list[dict]) -> str:
    """Month-by-month comparison: cost and consumption, then distance driven.

    The month rows come from the integration's own aggregation
    (``data.FuelUsage.months()``), not from a second implementation.
    """
    rows = list(reversed(months))  # chronological
    width, height = 960, 720
    x0, x1 = 84.0, 900.0
    y0, y1 = 96.0, 440.0  # cost bars + consumption line
    y2, y3 = 540.0, 664.0  # distance bars

    max_cost = max(row["cost"] for row in rows) * 1.3
    consumptions = [row["avg_consumption"] for row in rows if row["avg_consumption"]]
    low, high = min(consumptions) * 0.88, max(consumptions) * 1.08
    max_km = max(row["distance"] or 0 for row in rows) * 1.25

    total_km = sum(row["distance"] or 0 for row in rows)
    total_cost = sum(row["cost"] for row in rows)
    total_liters = sum(row["liters"] for row in rows)

    svg: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        'xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, sans-serif">',
        f'<rect width="{width}" height="{height}" rx="14" fill="#fff"/>',
        text(40, 46, f"{data['title']} — mjesečna usporedba ({len(rows)} mjeseci)",
             font_size="20", font_weight="600", fill=INK),
        text(40, 70,
             f"{hr(total_km, 0)} km · {hr(total_liters, 1)} L · {hr(total_cost)} € · "
             f"prosjek {hr(total_liters / total_km * 100)} L/100km",
             font_size="13", fill=MUTED),
    ]

    band = (x1 - x0) / len(rows)
    bar_w = band * 0.46

    # --- cost bars (left axis) + consumption line (right axis) ---------------
    for step in range(5):
        value = max_cost / 4 * step
        y = y1 - (y1 - y0) * step / 4
        svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}"/>')
        svg.append(text(x0 - 12, y + 4, f"{value:.0f}", font_size="11", fill=MUTED, text_anchor="end"))
    for step in range(5):
        value = low + (high - low) * step / 4
        y = y1 - (y1 - y0) * step / 4
        svg.append(text(x1 + 12, y + 4, hr(value, 1), font_size="11", fill=ORANGE, text_anchor="start"))
    svg.append(text(x0 - 12, y0 - 16, "€/mjesec", font_size="11", fill=MUTED, text_anchor="end"))
    svg.append(text(x1 + 12, y0 - 16, "L/100km", font_size="11", fill=ORANGE, text_anchor="start"))

    centers: list[float] = []
    previous_cost: float | None = None
    for index, row in enumerate(rows):
        center = x0 + band * (index + 0.5)
        centers.append(center)
        bar_h = (y1 - y0) * row["cost"] / max_cost
        svg.append(
            f'<rect x="{center - bar_w / 2:.1f}" y="{y1 - bar_h:.1f}" width="{bar_w:.1f}" '
            f'height="{bar_h:.1f}" rx="4" fill="{BLUE}" opacity="0.85"/>'
        )
        svg.append(text(center, y1 - bar_h - 6, hr(row["cost"], 0), font_size="11",
                        fill=BLUE, text_anchor="middle"))
        if previous_cost:
            delta = (row["cost"] - previous_cost) / previous_cost * 100
            svg.append(
                text(center, y1 + 14, f"{delta:+.0f}%", font_size="10",
                     fill=GREEN if delta <= 0 else "#d9534f", text_anchor="middle")
            )
        previous_cost = row["cost"]

    # Dashed segments mark months without a measured leg (gap in the line).
    segment = []
    for center, row in zip(centers, rows):
        if row["avg_consumption"] is None:
            if len(segment) > 1:
                svg.append(
                    '<path d="' + " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}"
                                           for i, (x, y, _) in enumerate(segment))
                    + f'" fill="none" stroke="{ORANGE}" stroke-width="2.5"/>'
                )
            segment = []
            continue
        py = y1 - (y1 - y0) * (row["avg_consumption"] - low) / (high - low)
        segment.append((center, py, row["avg_consumption"]))
        svg.append(f'<circle cx="{center:.1f}" cy="{py:.1f}" r="3.5" fill="#fff" '
                   f'stroke="{ORANGE}" stroke-width="2.5"/>')
    if len(segment) > 1:
        svg.append(
            '<path d="' + " ".join(f"{'M' if i == 0 else 'L'}{x:.1f} {y:.1f}"
                                   for i, (x, y, _) in enumerate(segment))
            + f'" fill="none" stroke="{ORANGE}" stroke-width="2.5"/>'
        )

    # --- distance bars -------------------------------------------------------
    svg.append(text(40, y2 - 26, "Prijeđeni kilometri po mjesecu", font_size="14",
                    font_weight="600", fill=INK))
    for center, row in zip(centers, rows):
        km = row["distance"] or 0
        bar_h = (y3 - y2) * km / max_km
        svg.append(
            f'<rect x="{center - bar_w / 2:.1f}" y="{y3 - bar_h:.1f}" width="{bar_w:.1f}" '
            f'height="{bar_h:.1f}" rx="4" fill="{GREEN}" opacity="0.85"/>'
        )
        svg.append(text(center, y3 - bar_h - 6, hr(km, 0), font_size="10.5",
                        fill=GREEN, text_anchor="middle"))
        svg.append(text(center, y3 + 20, row["month"][2:], font_size="11", fill=MUTED,
                        text_anchor="middle"))

    # --- legend --------------------------------------------------------------
    svg.append(f'<rect x="{x0}" y="{y3 + 40}" width="14" height="14" rx="3" fill="{BLUE}"/>')
    svg.append(text(x0 + 22, y3 + 52, "trošak goriva (€)", font_size="12", fill=MUTED))
    svg.append(f'<circle cx="{x0 + 200}" cy="{y3 + 47}" r="6" fill="#fff" stroke="{ORANGE}" '
               'stroke-width="2.5"/>')
    svg.append(text(x0 + 214, y3 + 52, "prosječna potrošnja (L/100km)", font_size="12", fill=MUTED))
    svg.append(f'<rect x="{x0 + 470}" y="{y3 + 40}" width="14" height="14" rx="3" fill="{GREEN}"/>')
    svg.append(text(x0 + 492, y3 + 52, "prijeđeni km", font_size="12", fill=MUTED))
    svg.append(text(x1, y3 + 52, "postotak iznad stupca = promjena troška prema prethodnom mjesecu",
                    font_size="11", fill=MUTED, text_anchor="end"))
    svg.append("</svg>")
    return (
        "<!doctype html>\n<html lang=\"hr\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Fuel Usage Tracker — mjesečna usporedba</title>\n"
        "<style>html,body{margin:0;padding:0;background:#f4f5f7}</style>\n</head>\n<body>\n"
        + "\n".join(svg) + "\n</body>\n</html>\n"
    )


def crop_to_content(path: Path) -> tuple[int, int]:
    """Drop the blank page area Chrome adds around the drawing.

    The screenshot window is deliberately larger than the page (Chrome's
    --window-size / device-scale-factor interaction is not worth predicting), so
    the PNG is trimmed to the drawing against the page-background colour.
    """
    from PIL import Image

    image = Image.open(path).convert("RGB")
    background = image.getpixel((2, 2))
    mask = Image.new("L", image.size)
    mask.putdata([0 if pixel == background else 255 for pixel in image.getdata()])
    box = mask.getbbox()
    if box is None:
        raise SystemExit(f"{path} rendered blank")
    image.crop(box).save(path)
    return image.crop(box).size


def main() -> None:
    if "--crop" in sys.argv:
        for name in ("monthly-chart.png", "architecture.png"):
            png = HERE.parent / "images" / name
            if png.exists():
                width, height = crop_to_content(png)
                print(f"cropped {png.name} -> {width}x{height}")
        return
    data = load()
    (HERE / "monthly-chart.html").write_text(monthly_chart_html(data, data["months"]))
    (HERE / "architecture.html").write_text(architecture_html(data["title"]))
    print(f"fill-ups: {len(data['fillups'])}, months: {len(data['months'])}")
    for row in data["months"]:
        print(
            f"  {row['month']}  {row['distance'] or 0:6.0f} km  {row['liters']:6.1f} L  "
            f"{row['cost']:7.2f} EUR  {row['avg_consumption'] or float('nan'):5.2f} L/100km  "
            f"{row['fill_count']} fills"
        )


if __name__ == "__main__":
    main()
