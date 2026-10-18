#!/usr/bin/env python3
"""Generate the preview diagrams (consumption chart + data flow) for the docs.

Reads the real exported HA sensor states from /tmp/fut_states.json and writes
two self-contained HTML pages next to this script:

    docs/preview/consumption-chart.html   -> docs/images/consumption-chart.png
    docs/preview/architecture.html        -> docs/images/architecture.png

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
      --window-size=2200,1800 --virtual-time-budget=1500 \
      --screenshot=docs/images/consumption-chart.png \
      "file://$PWD/docs/preview/consumption-chart.html"
    "$CHROME" --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
      --disable-crash-reporter --run-all-compositor-stages-before-draw \
      --user-data-dir="$(mktemp -d)" --force-device-scale-factor=2 \
      --window-size=2100,1400 --virtual-time-budget=1500 \
      --screenshot=docs/images/architecture.png \
      "file://$PWD/docs/preview/architecture.html"
    .venv/bin/python docs/preview/make_diagrams.py --crop     # trims the blank page area
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

STATES = Path("/tmp/fut_states.json")
HERE = Path(__file__).parent

CARD = "card-background-color"
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
    fillups = list(reversed(sensors["last_fill"]["attributes"]["fillups"]))
    for fill in fillups:
        fill["date"] = datetime.fromisoformat(str(fill["date"]).replace("Z", "+00:00"))
    return {"title": data["title"], "sensors": sensors, "fillups": fillups}


def legs(fillups: list[dict]) -> list[dict]:
    """Tank-to-tank legs, same rule as data.FuelUsage._legs()."""
    out: list[dict] = []
    previous: tuple[int, dict] | None = None
    for index, fill in enumerate(fillups):
        if not fill["full"]:
            continue
        if fill["odometer"] is None:
            previous = None
            continue
        if previous is not None:
            prev_index, prev = previous
            distance = fill["odometer"] - prev["odometer"]
            if distance > 0:
                liters = sum(item["liters"] for item in fillups[prev_index + 1 : index + 1])
                out.append(
                    {
                        "date": fill["date"],
                        "distance": distance,
                        "liters": liters,
                        "consumption": liters / distance * 100,
                    }
                )
        previous = (index, fill)
    return out


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


def chart_html(data: dict, leg_rows: list[dict]) -> str:
    title = data["title"]
    sensors = data["sensors"]
    fillups = data["fillups"]

    x0, x1 = 78.0, 880.0
    y0, y1 = 92.0, 452.0  # panel A plot area
    y2, y3 = 560.0, 700.0  # panel B plot area

    max_cons = max(row["consumption"] for row in leg_rows) * 1.35
    prices = [fill["price"] / fill["liters"] for fill in fillups]
    price_min, price_max = min(prices) * 0.94, max(prices) * 1.06
    total_cost = float(sensors["total_cost"]["state"])
    cum = 0.0
    cumulative: list[tuple[float, float]] = []
    for index, fill in enumerate(fillups):
        cum += fill["price"]
        cumulative.append((index, cum))

    svg: list[str] = [
        f'<svg viewBox="0 0 {CHART_W} {CHART_H}" width="{CHART_W}" height="{CHART_H}" '
        'xmlns="http://www.w3.org/2000/svg" font-family="system-ui, -apple-system, sans-serif">',
        f'<rect width="{CHART_W}" height="{CHART_H}" rx="14" fill="#fff"/>',
        text(40, 46, f"{title} — potrošnja, cijena i trošak kroz vrijeme",
             font_size="20", font_weight="600", fill=INK),
        text(40, 70,
             f"prosjek {float(sensors['avg_consumption']['state']):.2f} L/100km · "
             f"prosječna cijena {float(sensors['avg_price_per_liter']['state']):.2f} €/L · "
             f"{float(sensors['cost_per_km']['state']):.3f} €/km · "
             f"ukupno {total_cost:.2f} € kroz {float(sensors['total_distance']['state']):.0f} km",
             font_size="13", fill=MUTED),
    ]

    # --- panel A grid + axes -------------------------------------------------
    ticks = 5
    for step in range(ticks + 1):
        value = max_cons / ticks * step
        y = y1 - (y1 - y0) * step / ticks
        svg.append(
            f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>'
        )
        svg.append(text(x0 - 12, y + 4, f"{value:.0f}", font_size="11", fill=MUTED, text_anchor="end"))
    for step in range(ticks + 1):
        value = price_min + (price_max - price_min) * step / ticks
        y = y1 - (y1 - y0) * step / ticks
        svg.append(
            text(x1 + 12, y + 4, f"{value:.2f}", font_size="11", fill=ORANGE, text_anchor="start")
        )
    svg.append(text(x0 - 12, y0 - 18, "L/100km", font_size="11", fill=MUTED, text_anchor="end"))
    svg.append(text(x1 + 12, y0 - 18, "€/L", font_size="11", fill=ORANGE, text_anchor="start"))

    # --- panel A: consumption bars ------------------------------------------
    band = (x1 - x0) / len(leg_rows)
    bar_w = band * 0.44
    for index, row in enumerate(leg_rows):
        center = x0 + band * (index + 0.5)
        height = (y1 - y0) * row["consumption"] / max_cons
        svg.append(
            f'<rect x="{center - bar_w / 2:.1f}" y="{y1 - height:.1f}" width="{bar_w:.1f}" '
            f'height="{height:.1f}" rx="4" fill="{BLUE}" opacity="0.9"/>'
        )
        svg.append(
            text(center, y1 - height - 8, f"{row['consumption']:.2f}", font_size="12",
                 font_weight="600", fill=BLUE, text_anchor="middle")
        )
        svg.append(
            text(center, y1 + 20, row["date"].strftime("%d.%m.%Y"), font_size="11",
                 fill=MUTED, text_anchor="middle")
        )
        svg.append(
            text(center, y1 + 36, f"{row['distance']:.0f} km · {row['liters']:.1f} L",
                 font_size="10.5", fill=MUTED, text_anchor="middle")
        )

    # --- panel A: price per litre line --------------------------------------
    price_band = (x1 - x0) / len(fillups)
    points = []
    for index, fill in enumerate(fillups):
        price = fill["price"] / fill["liters"]
        px = x0 + price_band * (index + 0.5)
        py = y1 - (y1 - y0) * (price - price_min) / (price_max - price_min)
        points.append((px, py, price))
    path = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f} {py:.1f}" for i, (px, py, _) in enumerate(points))
    svg.append(f'<path d="{path}" fill="none" stroke="{ORANGE}" stroke-width="2.5"/>')
    for px, py, price in points:
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" fill="#fff" stroke="{ORANGE}" stroke-width="2.5"/>')
        svg.append(text(px, py - 12, f"{price:.2f}", font_size="10.5", fill=ORANGE, text_anchor="middle"))

    # --- panel B: cumulative cost -------------------------------------------
    max_cost = cumulative[-1][1] * 1.08
    for step in range(5):
        value = max_cost / 4 * step
        y = y3 - (y3 - y2) * step / 4
        svg.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        svg.append(text(x0 - 12, y + 4, f"{value:.0f}", font_size="11", fill=MUTED, text_anchor="end"))
    svg.append(text(x0 - 12, y2 - 18, "€ ukupno", font_size="11", fill=MUTED, text_anchor="end"))
    svg.append(text(40, y2 - 30, "Kumulativni trošak goriva", font_size="15", font_weight="600", fill=INK))

    cum_points = []
    for index, total in cumulative:
        px = x0 + price_band * (index + 0.5)
        py = y3 - (y3 - y2) * total / max_cost
        cum_points.append((px, py, total))
    area = (
        f"M{x0} {y3} "
        + " ".join(f"L{px:.1f} {py:.1f}" for px, py, _ in cum_points)
        + f" L{cum_points[-1][0]:.1f} {y3} Z"
    )
    svg.append(f'<path d="{area}" fill="{GREEN}" opacity="0.12"/>')
    svg.append(
        '<path d="'
        + " ".join(f"{'M' if i == 0 else 'L'}{px:.1f} {py:.1f}" for i, (px, py, _) in enumerate(cum_points))
        + f'" fill="none" stroke="{GREEN}" stroke-width="2.5"/>'
    )
    for index, (px, py, total) in enumerate(cum_points):
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{GREEN}"/>')
        if index in (0, len(cum_points) - 1):
            svg.append(
                text(px, py - 10, f"{total:.2f} €", font_size="11", font_weight="600",
                     fill=GREEN, text_anchor="middle")
            )
    svg.append(
        text(x1, y3 + 18,
             f"{len(fillups)} tankanja · {sum(f['liters'] for f in fillups):.1f} L · "
             f"prosjek {cumulative[-1][1] / len(fillups):.2f} € po tankanju",
             font_size="11", fill=MUTED, text_anchor="end")
    )

    # legend
    svg.append(f'<rect x="{x0}" y="{y1 + 54}" width="14" height="14" rx="3" fill="{BLUE}"/>')
    svg.append(text(x0 + 22, y1 + 66, "potrošnja po legu (full-to-full)", font_size="12", fill=MUTED))
    svg.append(f'<circle cx="{x0 + 250}" cy="{y1 + 61}" r="6" fill="#fff" stroke="{ORANGE}" stroke-width="2.5"/>')
    svg.append(text(x0 + 264, y1 + 66, "cijena po litri", font_size="12", fill=MUTED))
    svg.append("</svg>")

    return (
        "<!doctype html>\n<html lang=\"hr\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<title>Fuel Usage Tracker — graf potrošnje</title>\n"
        "<style>html,body{margin:0;padding:0;background:#f4f5f7}</style>\n</head>\n"
        "<body>\n" + "\n".join(svg) + "\n</body>\n</html>\n"
    )


def architecture_html(title: str) -> str:
    boxes = [
        ("Vozilo (config entry)\nnaziv · gorivo · motor · km", 40, 150, 190, 76, "#eef4ff", "#4f8ef7"),
        ("Servisi\nadd_fillup · update_fillup\ndelete_fillup · update_vehicle", 280, 150, 230, 76, "#fff7e6", ORANGE),
        ("Store po vozilu\n.storage/fuelusagetracker.<id>\nlitre · cijena · odometar · datum", 560, 150, 250, 76, "#eefaf3", GREEN),
        ("FuelUsage + koordinator\ntank-to-tank L/100km\n€/km · km · potrošnja", 560, 300, 250, 76, "#eefaf3", GREEN),
        ("14 senzora po vozilu\nsensor.fuelusagetracker_*", 280, 300, 230, 76, "#eef4ff", "#4f8ef7"),
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
        for name in ("consumption-chart.png", "architecture.png"):
            png = HERE.parent / "images" / name
            if png.exists():
                width, height = crop_to_content(png)
                print(f"cropped {png.name} -> {width}x{height}")
        return
    data = load()
    leg_rows = legs(data["fillups"])
    (HERE / "consumption-chart.html").write_text(chart_html(data, leg_rows))
    (HERE / "architecture.html").write_text(architecture_html(data["title"]))
    print(f"legs: {len(leg_rows)}, fill-ups: {len(data['fillups'])}")
    for row in leg_rows:
        print(f"  {row['date']:%d.%m.%Y}  {row['consumption']:.2f} L/100km  {row['distance']:.0f} km")


if __name__ == "__main__":
    main()
