/**
 * Fuel Usage Tracker card — vanilla JS, no build step.
 *
 * Everything is discovered from state attributes (key / vehicle / vehicle_name /
 * fuel_type / engine), never from guessed entity ids, so renamed entities keep
 * working. Fill-ups come from the `fillups` attribute of the `last_fill` entity;
 * writes go through the fuelusagetracker services.
 */

const CARD_TAG = "fuelusagetracker-card";
/** Kept in sync with manifest.json by scripts/release.sh; logged for cache hunts. */
const CARD_BUILD = "0.13.3";
const DOMAIN = "fuelusagetracker";

/**
 * One headline number (with the 12-month trend) and a row of icon chips. Each
 * entry is `{key, label, digits, money?, icon?}`; the key is the sensor's `key`
 * attribute, so nothing here depends on entity ids.
 */
const BIG = { key: "avg_consumption", label: "Avg consumption", digits: 2 };

const CHIPS = [
  { key: "cost_per_100km", label: "Cost / 100 km", digits: 2, money: true },
  { key: "last_consumption", label: "Last fill", digits: 2 },
  { key: "avg_price_per_liter", label: "Price / litre", digits: 3 },
  { key: "consumed_liters", label: "Consumed", digits: 2 },
  { key: "consumed_cost", label: "Fuel cost", digits: 2, money: true },
  { key: "total_distance", label: "Distance", digits: 0 },
  { key: "distance_to_last_fill", label: "Until last fill", digits: 0 },
  { key: "range_full_tank", label: "Range", digits: 0 },
  { key: "fill_count", label: "Fill-ups", digits: 0 },
  { key: "total_liters", label: "Bought", digits: 2 },
  { key: "total_cost", label: "Spent", digits: 2, money: true },
];

/** Two period cards: current period cost + consumption, each with its chip. */
const PERIOD_PANELS = [
  {
    title: "This month",
    cost: { key: "month_cost", label: "Cost", digits: 2, money: true, period: "month" },
    consumption: { key: "month_avg_consumption", label: "Consumption", digits: 2, period: "month" },
  },
  {
    title: "This year",
    cost: { key: "year_cost", label: "Cost", digits: 2, money: true, period: "year" },
    consumption: { key: "year_avg_consumption", label: "Consumption", digits: 2, period: "year" },
  },
];

/** Trailing-window strip: sensor key, field label, fraction digits, money flag. */
/** The 12-month chart can show any of these, switched by the segmented control. */
const TREND_SERIES = [
  { key: "avg_consumption", label: "L/100km", digits: 2, unit: "L/100km" },
  { key: "cost", label: "Cost", digits: 2, money: true },
  { key: "distance", label: "Distance", digits: 0, unit: "km" },
];

/** Small history sparklines: the four numbers that move month to month. */
const MINI_SERIES = [
  { key: "avg_consumption", label: "L/100km", digits: 2 },
  { key: "cost", label: "Cost", digits: 2, money: true },
  { key: "distance", label: "Distance", digits: 0 },
  { key: "price", label: "Price / L", digits: 3, money: true },
];

const ROLLING = [
  { key: "rolling_distance", label: "Distance", digits: 0 },
  { key: "rolling_liters", label: "Litres", digits: 2 },
  { key: "rolling_cost", label: "Cost", digits: 2, money: true },
  { key: "rolling_avg_consumption", label: "Consumption", digits: 2 },
];

/**
 * Comparison tables, both drawn by `_renderPeriodTable`: `rows` and `current`
 * name the attributes of `entity` carrying the period payloads and the period
 * the entity states refer to. `limit` is the collapsed row count; the years
 * payload is capped at `YEAR_HISTORY_YEARS` (10), so that table has no limit
 * and renders every row without a toggle.
 */
const PERIOD_TABLES = [
  {
    toggle: "months",
    entity: "month_cost",
    rows: "months",
    current: "month",
    header: "Month",
    title: "Monthly comparison",
    empty: "No monthly data yet.",
    limit: 12,
  },
  {
    toggle: "years",
    entity: "year_cost",
    rows: "years",
    current: "year",
    header: "Year",
    title: "Yearly comparison",
    empty: "No yearly data yet.",
  },
];

const STYLES = `
  :host { display: block; container-type: inline-size; }
  ha-card { overflow: hidden; }
  .header { display: flex; align-items: center; gap: 12px; padding: 12px 16px 0; flex-wrap: wrap; }
  .header .name { flex: 1 1 auto; font-size: 1.15rem; font-weight: 500; color: var(--primary-text-color); }
  /* Glow header: a gradient from the theme accent (no photo), a big number with
     a 12-month sparkline, and a row of glass icon chips. */
  .glow { position: relative; margin: 12px 16px 0; padding: 14px 16px 16px; border-radius: 18px; overflow: hidden;
    color: var(--text-primary-color, #fff);
    background:
      radial-gradient(120% 140% at 0% 0%, rgba(255, 255, 255, .22), rgba(255, 255, 255, 0) 55%),
      linear-gradient(135deg, rgba(var(--rgb-primary-color, 3, 169, 244), .95), rgba(var(--rgb-primary-color, 3, 169, 244), .55)); }
  .glow::after { content: ""; position: absolute; top: -40%; right: -10%; width: 60%; height: 140%;
    background: radial-gradient(closest-side, rgba(255, 255, 255, .28), rgba(255, 255, 255, 0)); pointer-events: none; }
  .glow-top { position: relative; z-index: 1; display: flex; align-items: center; gap: 12px; }
  .avatar { flex: 0 0 auto; display: grid; place-items: center; width: 44px; height: 44px; overflow: hidden;
    border-radius: 14px; background: rgba(255, 255, 255, .18); border: 1px solid rgba(255, 255, 255, .28); }
  .avatar img { width: 100%; height: 100%; object-fit: cover; }
  .avatar-letter { font-size: 1.1rem; font-weight: 600; color: currentColor; }
  .avatar img[hidden], .avatar-letter[hidden] { display: none; }
  .glow-id { flex: 1 1 auto; min-width: 0; }
  .vehicles { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; max-width: 55%; }
  .vehicle { padding: 3px 10px; border-radius: 999px; border: 1px solid rgba(255, 255, 255, .45);
    background: rgba(0, 0, 0, .18); color: inherit; font: inherit; font-size: .76rem; cursor: pointer;
    max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .vehicle:hover { background: rgba(0, 0, 0, .3); }
  .vehicle[aria-pressed="true"] { background: rgba(255, 255, 255, .92); color: #063a52; border-color: transparent; }
  .glow-name { font-size: 1.15rem; font-weight: 600; line-height: 1.2; overflow-wrap: anywhere; }
  .glow-sub { font-size: .8rem; opacity: .85; overflow-wrap: anywhere; }
  .glow-big { position: relative; z-index: 1; margin-top: 14px; }
  .big-label { font-size: .68rem; letter-spacing: .08em; text-transform: uppercase; opacity: .8; }
  .big-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
  .big-value { display: flex; align-items: baseline; gap: 6px; font-size: 2.6rem; font-weight: 600; line-height: 1; }
  .big-unit { font-size: .9rem; font-weight: 500; opacity: .85; }
  .spark { flex: 1 1 120px; max-width: 220px; height: 46px; color: currentColor; opacity: .9; }
  .big-delta { display: inline-block; margin-top: 7px; padding: 3px 9px; border-radius: 999px;
    font-size: .76rem; background: rgba(0, 0, 0, .18); }
  .big-delta:empty { display: none; }
  .big-delta.up { background: rgba(231, 76, 60, .42); }
  .big-delta.down { background: rgba(46, 204, 113, .42); }
  /* Mushroom-style chips: glass, icon in the accent colour, label over value. */
  .chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 16px 0; }
  .chip { display: inline-flex; align-items: center; padding: 5px 11px; border-radius: 999px;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), .10); border: 1px solid rgba(var(--rgb-primary-color, 3, 169, 244), .22);
    backdrop-filter: blur(10px) saturate(140%); -webkit-backdrop-filter: blur(10px) saturate(140%);
    transition: transform .15s ease, border-color .15s ease; }
  .chip:hover { transform: translateY(-1px); border-color: rgba(var(--rgb-primary-text-color, 33, 33, 33), .2); }
  .chip-text { display: flex; flex-direction: column; line-height: 1.15; }
  .chip-label { font-size: .62rem; letter-spacing: .06em; text-transform: uppercase; color: var(--secondary-text-color); }
  .chip-value { font-size: .88rem; color: var(--primary-text-color); }
  .chip-value .unit { margin-left: 4px; font-size: .72rem; color: var(--secondary-text-color); }
  /* Week/month cards: glass, with a share bar against the 12-month average. */
  .periods-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; padding: 10px 16px 12px; }
  .period-panel { position: relative; min-width: 0; padding: 12px 14px; border-radius: 16px;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), .10); border: 1px solid rgba(var(--rgb-primary-color, 3, 169, 244), .22);
    backdrop-filter: blur(10px) saturate(140%); -webkit-backdrop-filter: blur(10px) saturate(140%); }
  .panel-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    font-size: .66rem; letter-spacing: .07em; text-transform: uppercase; color: var(--secondary-text-color); }
  .panel-chip { margin-left: auto; }
  .panel-chip { padding: 0 7px; font-size: .64rem; letter-spacing: 0; text-transform: none; border-radius: 999px;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), .14); color: var(--primary-color); }
  .panel-chip:empty { display: none; }
  .period-panel .row { gap: 8px; font-size: .92rem; }
  .period-panel .row .v { overflow-wrap: anywhere; }
  .period-panel .row .v { font-weight: 600; }
  .ring-box { position: relative; flex: 0 0 auto; width: 32px; height: 32px; }
  .ring { width: 100%; height: 100%; transform: rotate(-90deg); }
  .ring circle { fill: none; stroke-width: 3; }
  .ring .ring-track { stroke: rgba(var(--rgb-primary-color, 3, 169, 244), .18); }
  .ring .ring-fill { stroke: var(--primary-color); stroke-linecap: round; transition: stroke-dashoffset .5s ease; }
  .ring-label { position: absolute; inset: 0; display: grid; place-items: center; font-size: .56rem; font-weight: 600; color: var(--primary-color); }
  /* History: a row of mini sparklines, then the bigger chart. */
  .history { padding: 14px 16px 12px; }
  .history-head { display: flex; align-items: center; justify-content: space-between; gap: 8px 12px; flex-wrap: wrap; margin-bottom: 8px; }
  .mini-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
  .mini-card { min-width: 0; padding: 8px 10px 6px; border-radius: 12px;
    background: rgba(var(--rgb-primary-color, 3, 169, 244), .08);
    border: 1px solid rgba(var(--rgb-primary-color, 3, 169, 244), .18); }
  .mini-label { font-size: .6rem; letter-spacing: .06em; text-transform: uppercase; color: var(--secondary-text-color); }
  .mini-row { display: flex; align-items: flex-end; justify-content: space-between; gap: 6px; }
  .mini-value { font-size: .92rem; color: var(--primary-text-color); }
  .mini { flex: 0 0 auto; width: 62px; height: 26px; color: var(--primary-color); }
  .mini .mini-area { fill: rgba(var(--rgb-primary-color, 3, 169, 244), .20); }
  .mini .mini-line { fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  @container (max-width: 519px) { .mini-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .trend { padding: 4px 16px 12px; }
  .trend-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
  .trend-title { font-weight: 500; color: var(--primary-text-color); }
  .segments { display: inline-flex; padding: 2px; gap: 2px; border-radius: 999px; background: rgba(var(--rgb-primary-color, 3, 169, 244), .12); }
  .segments button { padding: 3px 9px; border: 0; border-radius: 999px; background: none; color: var(--secondary-text-color); font: inherit; font-size: .72rem; cursor: pointer; }
  .segments button[aria-pressed="true"] { background: var(--primary-color); color: #fff; }
  .chart { display: block; width: 100%; height: 132px; overflow: visible; cursor: crosshair; color: var(--primary-color); }
  .chart .grid { stroke: rgba(var(--rgb-primary-text-color, 33, 33, 33), .10); stroke-width: 1; }
  .chart .axis { fill: var(--secondary-text-color); font-size: 9px; }
  .chart .area { fill: rgba(var(--rgb-primary-color, 3, 169, 244), .22); }
  .chart .line { fill: none; stroke: var(--primary-color); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
  .chart .dot { fill: var(--primary-color); }
  .chart .dot.picked { stroke: var(--card-background-color); stroke-width: 2; }
  .chart .hit { fill: transparent; }
  .trend-read { margin-top: 2px; font-size: .78rem; color: var(--secondary-text-color); min-height: 1.1em; }
  @container (max-width: 519px) {
    .glow-big { margin-top: 12px; }
    .big-value { font-size: 2.2rem; }
    .big-row { flex-direction: column; align-items: flex-start; gap: 4px; }
    .spark { flex: 0 0 auto; width: 100%; max-width: none; height: 38px; }
  }
  @media (prefers-reduced-motion: reduce) {
    .chip, .ring .ring-fill { transition: none; }
  }
  .section { border-top: 1px solid var(--divider-color); }
  .section-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 16px 6px; font-weight: 500; color: var(--primary-text-color); }
  .rows, form.grid, .actions, .fills { padding: 0 16px 12px; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 2px 0; font-size: .9rem; color: var(--primary-text-color); }
  .row .k { color: var(--secondary-text-color); }
  .row .v { text-align: right; }
  /* A unit inside a row value needs the same gap as in the figures. */
  .row .v .unit { margin-left: 3px; font-size: .72rem; color: var(--secondary-text-color); }
  form.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 8px; align-items: end; }
  .field { display: flex; flex-direction: column; gap: 3px; font-size: .75rem; color: var(--secondary-text-color); }
  .field.check { flex-direction: row; align-items: center; gap: 6px; padding-bottom: 7px; font-size: .85rem; }
  input { box-sizing: border-box; min-width: 0; width: 100%; padding: 6px 8px; font: inherit; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 6px; }
  input[type="checkbox"] { width: auto; }
  button { padding: 6px 12px; font: inherit; cursor: pointer; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 6px; }
  button.primary { color: var(--text-primary-color, #fff); background: var(--primary-color); border-color: var(--primary-color); }
  button.link { padding: 2px 6px; font-size: .8rem; border-color: transparent; background: transparent; color: var(--primary-color); }
  button.danger { padding: 4px 10px; color: var(--error-color, #db4437); border-color: var(--error-color, #db4437); background: transparent; }
  button[disabled] { opacity: .5; cursor: default; }
  .fills { display: flex; flex-direction: column; }
  .fill { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; padding: 8px 0; border-top: 1px solid var(--divider-color); }
  .fill:first-child { border-top: none; }
  .fill .main { grid-column: 1; font-size: .95rem; color: var(--primary-text-color); }
  .fill .meta, .fill .leg { grid-column: 1; font-size: .78rem; color: var(--secondary-text-color); }
  .fill button { grid-area: 1 / 2 / span 3 / 3; align-self: center; }
  .empty, .error, .notice { padding: 0 16px 12px; font-size: .85rem; }
  .empty, .notice { color: var(--secondary-text-color); }
  .error { color: var(--error-color, #db4437); }
  [hidden] { display: none; }
  .rolling { display: flex; flex-wrap: wrap; gap: 2px 14px; padding: 0 16px 12px; font-size: .85rem; color: var(--primary-text-color); }
  .rolling .window, .rolling .k { color: var(--secondary-text-color); }
  .rolling .k { margin-right: 4px; }
  .periods { padding: 0 16px 12px; }
  .periods-table { width: 100%; table-layout: fixed; border-collapse: collapse; font-size: .8rem; }
  .periods-table th, .periods-table td { padding: 3px 4px; text-align: right; vertical-align: top; overflow-wrap: anywhere; }
  .periods-table th:first-child, .periods-table td:first-child { width: 26%; text-align: left; }
  .periods-table thead th { font-size: .66rem; font-weight: 500; letter-spacing: .03em; text-transform: uppercase; color: var(--secondary-text-color); }
  .periods-table tbody tr { border-top: 1px solid var(--divider-color); }
  .periods-table tbody tr:first-child { border-top: none; }
  .periods-table .delta { font-size: .72rem; color: var(--secondary-text-color); }
  .periods-table tr.current td { color: var(--primary-text-color); }
  .periods-table tr.current td:first-child { font-weight: 600; }
  .periods-table .now { margin-left: 4px; padding: 0 4px; font-size: .64rem; font-weight: 400; letter-spacing: .03em; text-transform: uppercase; border-radius: 6px; background: var(--secondary-background-color); color: var(--secondary-text-color); }
`;

/** Create an element; `text`, `class` and `on*` keys get special treatment. */
function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child) node.append(child);
  return node;
}

function field(label, input, isCheck = false) {
  const node = el("label", { class: isCheck ? "field check" : "field" }, [
    input,
    el("span", { text: label }),
  ]);
  return node;
}

/** Donut ring: the share of the usual cost, with the percentage in the middle. */
function ring() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "ring");
  svg.setAttribute("viewBox", "0 0 36 36");
  svg.setAttribute("aria-hidden", "true");
  const CIRCUMFERENCE = 2 * Math.PI * 15;
  for (const [cls, offset] of [["ring-track", 0], ["ring-fill", CIRCUMFERENCE]]) {
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("class", cls);
    circle.setAttribute("cx", "18");
    circle.setAttribute("cy", "18");
    circle.setAttribute("r", "15");
    if (cls === "ring-fill") {
      circle.setAttribute("stroke-dasharray", CIRCUMFERENCE.toFixed(2));
      circle.setAttribute("stroke-dashoffset", offset.toFixed(2));
    }
    svg.append(circle);
  }
  const label = el("span", { class: "ring-label" });
  return { box: el("div", { class: "ring-box" }, [svg, label]), fill: svg.querySelector(".ring-fill"), label };
}

/** The 12-month chart skeleton: grid, gradient area, line, dots, hit area. */
function trendChart() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "chart");
  svg.setAttribute("viewBox", "0 0 320 132");
  svg.setAttribute("preserveAspectRatio", "none");
  const grid = document.createElementNS(ns, "g");
  grid.setAttribute("class", "grid");
  for (const y of [12, 52, 92]) {
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", "4");
    line.setAttribute("x2", "316");
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    grid.append(line);
  }
  const area = document.createElementNS(ns, "path");
  area.setAttribute("class", "area");
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "line");
  const dots = document.createElementNS(ns, "g");
  const hit = document.createElementNS(ns, "rect");
  hit.setAttribute("class", "hit");
  hit.setAttribute("x", "4");
  hit.setAttribute("y", "4");
  hit.setAttribute("width", "312");
  hit.setAttribute("height", "108");
  svg.append(grid, area, line, dots, hit);
  return { node: svg, area, line, dots, hit };
}

/** Tiny sparkline for one history metric. */
function miniChart() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "mini");
  svg.setAttribute("viewBox", "0 0 62 26");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  const area = document.createElementNS(ns, "path");
  area.setAttribute("class", "mini-area");
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "mini-line");
  svg.append(area, line);
  return { node: svg, area, line };
}

/** Plain svg container for the header's 12-month bar mini-chart. */
function barChart() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", "0 0 120 44");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  return svg;
}

/** Donut ring: the share of the usual cost, with the percentage in the middle. */
function ring() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "ring");
  svg.setAttribute("viewBox", "0 0 36 36");
  svg.setAttribute("aria-hidden", "true");
  const CIRCUMFERENCE = 2 * Math.PI * 15;
  for (const [cls, offset] of [["ring-track", 0], ["ring-fill", CIRCUMFERENCE]]) {
    const circle = document.createElementNS(ns, "circle");
    circle.setAttribute("class", cls);
    circle.setAttribute("cx", "18");
    circle.setAttribute("cy", "18");
    circle.setAttribute("r", "15");
    if (cls === "ring-fill") {
      circle.setAttribute("stroke-dasharray", CIRCUMFERENCE.toFixed(2));
      circle.setAttribute("stroke-dashoffset", offset.toFixed(2));
    }
    svg.append(circle);
  }
  const label = el("span", { class: "ring-label" });
  return { box: el("div", { class: "ring-box" }, [svg, label]), fill: svg.querySelector(".ring-fill"), label };
}

/** The 12-month chart skeleton: grid, gradient area, line, dots, hit area. */
function trendChart() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "chart");
  svg.setAttribute("viewBox", "0 0 320 132");
  svg.setAttribute("preserveAspectRatio", "none");
  const grid = document.createElementNS(ns, "g");
  grid.setAttribute("class", "grid");
  for (const y of [12, 52, 92]) {
    const line = document.createElementNS(ns, "line");
    line.setAttribute("x1", "4");
    line.setAttribute("x2", "316");
    line.setAttribute("y1", y);
    line.setAttribute("y2", y);
    grid.append(line);
  }
  const area = document.createElementNS(ns, "path");
  area.setAttribute("class", "area");
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "line");
  const dots = document.createElementNS(ns, "g");
  const hit = document.createElementNS(ns, "rect");
  hit.setAttribute("class", "hit");
  hit.setAttribute("x", "4");
  hit.setAttribute("y", "4");
  hit.setAttribute("width", "312");
  hit.setAttribute("height", "108");
  svg.append(grid, area, line, dots, hit);
  return { node: svg, area, line, dots, hit };
}

/** Sparkline skeleton: area + line + end dot, coloured by the surrounding text. */
function sparkline() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("viewBox", "0 0 120 44");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.setAttribute("aria-hidden", "true");
  const area = document.createElementNS(ns, "path");
  area.setAttribute("class", "spark-area");
  area.setAttribute("fill", "url(#fut-spark)");
  const line = document.createElementNS(ns, "path");
  line.setAttribute("class", "spark-line");
  line.setAttribute("fill", "none");
  const dot = document.createElementNS(ns, "circle");
  dot.setAttribute("class", "spark-dot");
  dot.setAttribute("r", "2.4");
  svg.append(defs, area, line, dot);
  return { node: svg, area, line, dot };
}

console.info("[fuelusagetracker-card] build", CARD_BUILD);

class FuelUsageTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._built = false;
    this._selected = null;
    this._showAll = {};
    this._busy = false;
    this._error = null;
    this._errorIsNotice = false;
    this._trendIndex = 0;
    this._trendPick = null;
    this._trendRows = [];
    this._trendRange = 12;
  }

  static getStubConfig(hass) {
    const vehicles = discoverVehicles(hass);
    const vehicle = vehicles[0];
    const entity = vehicle && Object.values(vehicle.keys)[0];
    return entity ? { entity } : {};
  }

  setConfig(config) {
    this._config = config || {};
    this._selected = null;
    this._built = false;
    if (this._hass) this._sync();
  }

  set hass(hass) {
    this._hass = hass;
    if (hass) this._sync();
  }

  getCardSize() {
    // The 200 px hero plus the figures row and the two period panels.
    return 8 + Math.min(4, this._displayedFills || 0);
  }

  // --- data discovery ------------------------------------------------------

  _discover() {
    return discoverVehicles(this._hass);
  }

  _vehicle() {
    return this._discover().find((vehicle) => vehicle.id === this._vehId);
  }

  _savedVehicle() {
    try {
      return window.localStorage.getItem("fuelusagetracker.vehicle");
    } catch (err) {
      return null;
    }
  }

  _currentVehicle(vehicles) {
    const config = this._config || {};
    const saved = this._selected || this._savedVehicle();
    if (saved) {
      const match = vehicles.find((vehicle) => vehicle.id === saved);
      if (match) return match;
    }
    if (this._selected) {
      const selected = vehicles.find((vehicle) => vehicle.id === this._selected);
      if (selected) return selected;
    }
    if (config.entity) {
      const state = this._hass.states[config.entity];
      const id = state && state.attributes && state.attributes.vehicle;
      const match = id && vehicles.find((vehicle) => vehicle.id === id);
      if (match) return match;
    }
    if (config.vehicle) {
      const needle = String(config.vehicle).trim().toLowerCase();
      const match = vehicles.find(
        (vehicle) =>
          vehicle.id.toLowerCase() === needle ||
          vehicle.name.toLowerCase() === needle
      );
      if (match) return match;
    }
    return vehicles[0];
  }

  _entity(vehicle, key) {
    const entityId = vehicle.keys[key];
    return entityId ? this._hass.states[entityId] : undefined;
  }

  _fillups(vehicle) {
    const state = this._entity(vehicle, "last_fill");
    const list = state && state.attributes && state.attributes.fillups;
    return Array.isArray(list) ? list : [];
  }

  _currency(vehicle) {
    const unit = this._unit(this._entity(vehicle, "total_cost"));
    return unit.split("/")[0].trim() || (this._hass.config && this._hass.config.currency) || "";
  }

  /** The last 12 month rows (oldest first) with a usable consumption value. */
  _history(vehicle) {
    const state = this._entity(vehicle, "month_cost");
    const rows = (state && state.attributes && state.attributes.months) || [];
    return rows
      .slice(0, 24)
      .reverse()
      .map((row) => ({
        period: String(row.period || ""),
        cost: Number(row.cost),
        distance: Number(row.distance),
        liters: Number(row.liters),
        avg_consumption: Number(row.avg_consumption),
      }))
      .filter((row) => row.period);
  }

  /** Pull one history metric out of a month row (price is derived). */
  _seriesValue(row, series) {
    if (series.key === "price") return row.liters > 0 ? row.cost / row.liters : NaN;
    return row[series.key];
  }

  /** Draw one mini sparkline (area + line) from a list of values. */
  _drawMini(chart, values) {
    const points = values.filter((value) => Number.isFinite(value));
    if (points.length < 2) {
      chart.line.setAttribute("d", "");
      chart.area.setAttribute("d", "");
      return;
    }
    const WIDTH = 62;
    const HEIGHT = 26;
    const PAD = 2;
    const min = Math.min(...points);
    const span = Math.max(...points) - min || 1;
    const mapped = points.map((value, index) => [
      PAD + (index / (points.length - 1)) * (WIDTH - PAD * 2),
      HEIGHT - PAD - ((value - min) / span) * (HEIGHT - PAD * 2),
    ]);
    const line = mapped
      .map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`)
      .join(" ");
    const last = mapped[mapped.length - 1];
    chart.line.setAttribute("d", line);
    chart.area.setAttribute("d", `${line} L${last[0].toFixed(1)},${HEIGHT} L${mapped[0][0].toFixed(1)},${HEIGHT} Z`);
  }

  /** History block: four mini sparklines plus the bigger trend chart. */
  _renderHistory(vehicle) {
    const refs = this._refs.minis;
    const rows = this._history(vehicle).slice(-12);
    const currency = this._currency(vehicle);
    for (const series of MINI_SERIES) {
      const ref = refs && refs[series.key];
      if (!ref) continue;
      const values = rows.map((row) => this._seriesValue(row, series));
      this._drawMini(ref.chart, values);
      const usable = values.filter((value) => Number.isFinite(value));
      const last = usable[usable.length - 1];
      const previous = usable[usable.length - 2];
      ref.value.textContent = Number.isFinite(last)
        ? series.money
          ? this._money(last, currency)
          : this._number(last, series.digits)
        : "-";
      const diff = Number.isFinite(last) && Number.isFinite(previous) ? last - previous : null;
      if (diff === null) {
        ref.delta.textContent = "";
        ref.delta.className = "mini-delta";
      } else {
        ref.delta.textContent = `${diff > 0 ? "▲" : "▼"} ${
          series.money ? this._money(Math.abs(diff), currency) : this._number(Math.abs(diff), series.digits)
        }`;
        ref.delta.className = "mini-delta";
      }
    }
    this._renderTrend(vehicle);
  }

  /** The glow header's 12-month cost bars; hidden while there is nothing to plot. */
  _drawBars(spark, rows) {
    if (rows.length < 2) {
      spark.style.display = "none";
      return;
    }
    spark.style.display = "";
    spark.textContent = "";
    const ns = "http://www.w3.org/2000/svg";
    const values = rows.map((row) => (Number.isFinite(row.cost) ? row.cost : 0));
    const max = Math.max(...values) || 1;
    const gap = 2;
    const width = (120 - gap * (values.length - 1)) / values.length;
    values.forEach((value, index) => {
      const height = Math.max(2, (value / max) * 40);
      const rect = document.createElementNS(ns, "rect");
      rect.setAttribute("x", (index * (width + gap)).toFixed(1));
      rect.setAttribute("y", (44 - height).toFixed(1));
      rect.setAttribute("width", width.toFixed(1));
      rect.setAttribute("height", height.toFixed(1));
      rect.setAttribute("rx", "1.3");
      rect.setAttribute("fill", "currentColor");
      rect.setAttribute("opacity", index === values.length - 1 ? "1" : ".5");
      spark.append(rect);
    });
  }

  /** Draw the 12-month trend for the selected series and the tapped month. */
  _renderTrend(vehicle) {
    const refs = this._refs.trend;
    const series = TREND_SERIES[this._trendIndex] || TREND_SERIES[0];
    const range = this._trendRange || 12;
    const rows = this._history(vehicle)
      .slice(-range)
      .filter((row) => Number.isFinite(row[series.key]));
    this._trendRows = rows;
    if (rows.length < 2) {
      refs.node.style.display = "none";
      refs.read.textContent = "Not enough history for a chart yet.";
      return;
    }
    refs.node.style.display = "";
    const LEFT = 4;
    const RIGHT = 316;
    const TOP = 8;
    const BOTTOM = 100;
    const values = rows.map((row) => row[series.key]);
    const min = Math.min(...values);
    const span = Math.max(...values) - min || 1;
    const points = values.map((value, index) => [
      LEFT + (index / (values.length - 1)) * (RIGHT - LEFT),
      BOTTOM - ((value - min) / span) * (BOTTOM - TOP),
    ]);
    const path = points
      .map(([x, y], index) => `${index ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`)
      .join(" ");
    refs.line.setAttribute("d", path);
    refs.area.setAttribute("d", `${path} L${RIGHT},${BOTTOM} L${LEFT},${BOTTOM} Z`);
    const picked = this._trendPick === null ? points.length - 1 : Math.min(points.length - 1, Math.max(0, this._trendPick));
    refs.dots.textContent = "";
    const ns = "http://www.w3.org/2000/svg";
    points.forEach(([x, y], index) => {
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("class", index === picked ? "dot picked" : "dot");
      dot.setAttribute("cx", x.toFixed(1));
      dot.setAttribute("cy", y.toFixed(1));
      dot.setAttribute("r", index === picked ? "3.4" : "1.8");
      dot.setAttribute("opacity", index === picked ? "1" : ".5");
      refs.dots.append(dot);
    });
    const row = rows[picked];
    const currency = this._currency(vehicle);
    const value = series.money
      ? this._money(row[series.key], currency)
      : `${this._number(row[series.key], series.digits)} ${series.unit}`;
    refs.read.textContent = `${this._periodLabel(row.period)} · ${value}`;
  }

  /** Hero background: the config override first, else the vehicle's entity_picture. */
  _image(vehicle) {
    if (this._config && this._config.image) return String(this._config.image);
    const state = this._entity(vehicle, "odometer");
    return (state && state.attributes && state.attributes.entity_picture) || "";
  }

  // --- formatting ---------------------------------------------------------

  _locale() {
    return (
      (this._hass.locale && this._hass.locale.language) ||
      this._hass.language ||
      undefined
    );
  }

  _number(value, digits = 2) {
    if (!Number.isFinite(value)) return "-";
    const options = { maximumFractionDigits: digits };
    try {
      if (typeof this._hass.formatNumber === "function") {
        return this._hass.formatNumber(value, options);
      }
      return new Intl.NumberFormat(this._locale(), options).format(value);
    } catch (err) {
      return value.toFixed(digits);
    }
  }

  _money(value, currency) {
    if (!Number.isFinite(value)) return "-";
    const code = (currency || "").trim();
    if (code) {
      try {
        return new Intl.NumberFormat(this._locale(), {
          style: "currency",
          currency: code,
          maximumFractionDigits: 2,
        }).format(value);
      } catch (err) {
        /* unknown currency code: fall through to a plain number */
      }
    }
    return this._number(value, 2) + (code ? ` ${code}` : "");
  }

  _value(state, digits, currency) {
    if (!state || ["unknown", "unavailable", ""].includes(state.state)) return "-";
    const value = Number(state.state);
    if (!Number.isFinite(value)) return state.state;
    return currency ? this._money(value, currency) : this._number(value, digits);
  }

  _unit(state) {
    return (state && state.attributes && state.attributes.unit_of_measurement) || "";
  }

  _date(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    try {
      return new Intl.DateTimeFormat(this._locale(), {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(date);
    } catch (err) {
      return date.toLocaleString();
    }
  }

  _localDatetime(date = new Date()) {
    const pad = (part) => String(part).padStart(2, "0");
    return (
      `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
      `T${pad(date.getHours())}:${pad(date.getMinutes())}`
    );
  }

  // --- rendering ----------------------------------------------------------

  _sync() {
    if (!this._hass) return;
    try {
      this._syncState();
    } catch (err) {
      // Home Assistant renders a bare "Configuration error" when setConfig
      // throws, which hides the actual exception (notably in the companion
      // apps). Show it instead, and keep logging it.
      this._renderFailure(err);
    }
  }

  _syncState() {
    if (!this._built) {
      this._render();
      return;
    }
    const vehicle = this._vehicle();
    const current = this._currentVehicle(this._discover());
    if (!vehicle || !current || current.id !== vehicle.id) this._render();
    else this._update(vehicle);
  }

  _renderFailure(err) {
    console.error("[fuelusagetracker-card]", err);
    const message = String((err && err.message) || err || "unknown error");
    const root = this.shadowRoot || this.attachShadow({ mode: "open" });
    root.innerHTML = "";
    const card = el("ha-card");
    const box = el("div", { class: "error" });
    box.append(
      el("div", { text: "Fuel Usage Tracker could not render this card." }),
      el("div", { text: message }),
      el("div", { text: "The full details are in the browser/app console (search for fuelusagetracker-card)." })
    );
    card.append(box);
    root.append(el("style", { text: STYLES }), card);
  }

  _render() {
    const vehicles = this._discover();
    const vehicle = this._currentVehicle(vehicles);
    const root = this.shadowRoot;
    root.innerHTML = "";
    root.append(el("style", { text: STYLES }));

    const card = el("ha-card");
    root.append(card);

    if (!vehicle) {
      card.append(
        el("div", { class: "header" }, [el("span", { class: "name", text: "Fuel Usage Tracker" })]),
        el("div", { class: "empty", text: "No tracked vehicle found. Add one in Settings → Devices & services." })
      );
      this._built = true;
      this._vehId = null;
      this._refs = { fillNodes: [] };
      return;
    }

    this._vehId = vehicle.id;
    this._built = true;

    // One map for every value the card shows; each entry owns its own nodes.
    const values = {};
    const valueParts = (stat) => {
      const amount = el("span");
      const unit = el("span", { class: "unit" });
      values[stat.key] = { amount, unit, chip: null, stat };
      return [amount, unit];
    };
    const valueNode = (stat, className) =>
      el("div", { class: className }, [
        el("div", { class: "label", text: stat.label }),
        el("div", { class: "value" }, valueParts(stat)),
      ]);
    const valueRow = (stat) =>
      el("div", { class: "row" }, [
        el("span", { class: "k", text: stat.label }),
        el("span", { class: "v" }, valueParts(stat)),
      ]);

    // Glow header: avatar, identity, headline number with the 12-month trend.
    const glow = el("div", { class: "glow" });
    const avatarImg = el("img", { alt: "" });
    const avatarLetter = el("span", { class: "avatar-letter" });
    const avatar = el("div", { class: "avatar" }, [avatarImg, avatarLetter]);
    const glowName = el("div", { class: "glow-name", text: vehicle.name });
    const glowSub = el("div", { class: "glow-sub" });
    const bigAmount = el("span");
    const bigUnit = el("span", { class: "big-unit" });
    values[BIG.key] = { amount: bigAmount, unit: bigUnit, chip: null, stat: BIG };
    const bigDelta = el("div", { class: "big-delta" });
    const spark = barChart();
    const glowTop = el("div", { class: "glow-top" }, [
      avatar,
      el("div", { class: "glow-id" }, [glowName, glowSub]),
    ]);
    glow.append(
      glowTop,
      el("div", { class: "glow-big" }, [
        el("div", { class: "big-label", text: BIG.label }),
        el("div", { class: "big-row" }, [
          el("div", { class: "big-value" }, [bigAmount, bigUnit]),
          spark.node,
        ]),
        bigDelta,
      ])
    );
    if (vehicles.length > 1) {
      // One chip per vehicle: a tap selects it, no hidden menu to fight focus.
      glowTop.append(
        el(
          "div",
          { class: "vehicles", role: "group", "aria-label": "Vehicles" },
          vehicles.map((item) =>
            el("button", {
              class: "vehicle",
              type: "button",
              "aria-pressed": item.id === vehicle.id ? "true" : "false",
              text: item.name,
              onclick: () => this._selectVehicle(item.id),
            })
          )
        )
      );
    }

    // One icon chip per remaining figure, then the two period cards.
    const chips = el("div", { class: "chips" });
    for (const stat of CHIPS) {
      const amount = el("span");
      const unit = el("span", { class: "unit" });
      values[stat.key] = { amount, unit, chip: null, stat };
      chips.append(
        el("div", { class: "chip" }, [
          el("span", { class: "chip-text" }, [
            el("span", { class: "chip-label", text: stat.label }),
            el("span", { class: "chip-value" }, [amount, unit]),
          ]),
        ])
      );
    }

    const miniRefs = {};
    const summary = el("div", { class: "periods-summary" });
    const panelBars = {};
    for (const panel of PERIOD_PANELS) {
      const chip = el("span", { class: "panel-chip" });
      const costRow = valueRow(panel.cost);      // registers values[cost.key]
      const consumptionRow = valueRow(panel.consumption);
      const progress = ring();
      panelBars[panel.cost.key] = progress;
      values[panel.cost.key].chip = chip;
      summary.append(
        el("div", { class: "period-panel" }, [
          el("div", { class: "panel-head" }, [progress.box, el("span", { text: panel.title }), chip]),
          costRow,
          consumptionRow,
        ])
      );
    }

    const segments = TREND_SERIES.map((series, index) =>
      el("button", {
        type: "button",
        "aria-pressed": index === this._trendIndex ? "true" : "false",
        text: series.label,
        onclick: () => {
          this._trendIndex = index;
          this._trendPick = null;
          segments.forEach((node, i) => node.setAttribute("aria-pressed", String(i === index)));
          this._renderHistory(vehicle);
        },
      })
    );
    const chart = trendChart();
    const trendRead = el("div", { class: "trend-read" });
    const pick = (event) => {
      const box = chart.node.getBoundingClientRect();
      if (!box.width || this._trendRows.length < 2) return;
      const ratio = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width));
      this._trendPick = Math.round(ratio * (this._trendRows.length - 1));
      this._renderHistory(vehicle);
    };
    chart.hit.addEventListener("pointerdown", pick);
    chart.hit.addEventListener("pointermove", pick);
    const ranges = [12, 24].map((months) =>
      el("button", {
        type: "button",
        "aria-pressed": months === this._trendRange ? "true" : "false",
        text: months === 24 ? "24M" : "12M",
        onclick: () => {
          this._trendRange = months;
          this._trendPick = null;
          ranges.forEach((node, i) => node.setAttribute("aria-pressed", String([12, 24][i] === months)));
          this._renderHistory(vehicle);
        },
      })
    );
    const minis = MINI_SERIES.map((series) => {
      const value = el("span", { class: "mini-value" });
      const delta = el("span", { class: "mini-delta" });
      const mini = miniChart();
      miniRefs[series.key] = { chart: mini, value, delta, series };
      return el("div", { class: "mini-card" }, [
        el("span", { class: "mini-label", text: series.label }),
        el("div", { class: "mini-row" }, [value, mini.node]),
        delta,
      ]);
    });
    const historyNode = el("div", { class: "history" }, [
      el("div", { class: "history-head" }, [
        el("span", { class: "trend-title", text: "History" }),
        el("div", { class: "segments" }, segments),
        el("div", { class: "segments" }, ranges),
      ]),
      el("div", { class: "mini-grid" }, minis),
      chart.node,
      trendRead,
    ]);

    const error = el("div", { class: "error", hidden: "" });
    card.append(glow, error, chips, summary, historyNode);

    // Trailing-window strip; hidden entirely when the rolling_* sensors are absent.
    const rollingWindow = el("span", { class: "window" });
    const rollingFields = {};
    const rollingStrip = el("div", { class: "rolling" }, [rollingWindow]);
    for (const item of ROLLING) {
      const value = el("span", { class: "v" });
      rollingFields[item.key] = value;
      rollingStrip.append(
        el("span", { class: "rfield" }, [el("span", { class: "k", text: item.label }), value])
      );
    }
    const rollingSection = el("div", { class: "section" }, [
      el("div", { class: "section-head" }, [el("span", { text: "Last 12 months" })]),
      rollingStrip,
    ]);
    card.append(rollingSection);

    // Last fill details.
    const lastRows = el("div", { class: "rows" });
    const lastRefs = {};
    for (const [key, label] of [
      ["date", "Date"],
      ["liters", "Litres"],
      ["price", "Total price"],
      ["price_per_liter", "Price per litre"],
      ["odometer", "Odometer"],
      ["station", "Station"],
      ["tank", "Tank"],
      ["notes", "Notes"],
    ]) {
      const value = el("span", { class: "v" });
      lastRows.append(
        el("div", { class: "row" }, [el("span", { class: "k", text: label }), value])
      );
      lastRefs[key] = value;
    }
    card.append(
      el("div", { class: "section" }, [
        el("div", { class: "section-head" }, [el("span", { text: "Last fill" })]),
        lastRows,
      ])
    );

    // Odometer update. `step: any` because odometers can be fractional and a
    // step anchored at 0 would reject e.g. 128450.5 as a mismatch.
    const odoInput = el("input", { type: "number", min: "0", step: "any", inputmode: "decimal", placeholder: "km" });
    const odoButton = el("button", { class: "primary", type: "button", text: "Update odometer", onclick: () => this._updateOdometer() });
    card.append(
      el("div", { class: "section" }, [
        el("div", { class: "section-head" }, [el("span", { text: "Odometer" })]),
        el("form", { class: "grid", onsubmit: (event) => { event.preventDefault(); this._updateOdometer(); } }, [
          field("Current odometer (km)", odoInput),
          el("div", { class: "actions" }, [odoButton]),
        ]),
      ])
    );

    // Add fill-up.
    const inputs = {
      date: el("input", { type: "datetime-local", value: this._localDatetime() }),
      // `min` is the step base in HTML number inputs: with min 0.001 a plain
      // 45.20 is a step mismatch and the browser demands three decimals. Two
      // decimals are enough for a fill-up, so the base is 0.01 itself.
      liters: el("input", { type: "number", min: "0.01", step: "0.01", inputmode: "decimal", required: "" }),
      price: el("input", { type: "number", min: "0", step: "0.01", inputmode: "decimal", required: "" }),
      odometer: el("input", { type: "number", min: "0", step: "any", inputmode: "decimal" }),
      full: el("input", { type: "checkbox", checked: "" }),
      station: el("input", { type: "text" }),
    };
    const addButton = el("button", { class: "primary", type: "submit", text: "Add fill-up" });
    card.append(
      el("div", { class: "section" }, [
        el("div", { class: "section-head" }, [el("span", { text: "Add fill-up" })]),
        el("form", { class: "grid", onsubmit: (event) => { event.preventDefault(); this._addFillup(); } }, [
          field("Date", inputs.date),
          field("Litres", inputs.liters),
          field("Total price", inputs.price),
          field("Odometer (km, optional)", inputs.odometer),
          field("Full tank", inputs.full, true),
          field("Station (optional)", inputs.station),
          el("div", { class: "actions" }, [addButton]),
        ]),
      ])
    );

    // Collapsible lists; each section head carries the shared Show all toggle.
    const toggles = {};
    const tables = {};
    const fillNodes = el("div", { class: "fills" });
    card.append(
      el("div", { class: "section" }, [
        this._showAllHead("fills", "Recent fill-ups", toggles),
        fillNodes,
      ])
    );
    for (const table of PERIOD_TABLES) {
      const nodes = el("div", { class: "periods" });
      tables[table.toggle] = nodes;
      card.append(
        el("div", { class: "section" }, [
          this._showAllHead(table.toggle, table.title, toggles, Boolean(table.limit)),
          nodes,
        ])
      );
    }

    // CSV export of the fill-up log.
    const exportButton = el("button", {
      type: "button",
      text: "Export fill-ups (CSV)",
      onclick: () => this._exportCsv(),
    });
    card.append(
      el("div", { class: "section" }, [
        el("div", { class: "section-head" }, [el("span", { text: "CSV export" })]),
        el("div", { class: "actions" }, [exportButton]),
      ])
    );

    this._refs = {
      error,
      values,
      glow: { name: glowName, sub: glowSub, avatarImg, avatarLetter },
      big: { amount: bigAmount, unit: bigUnit, delta: bigDelta },
      spark,
      panels: panelBars,
      trend: { node: chart.node, area: chart.area, line: chart.line, dots: chart.dots, read: trendRead },
      minis: miniRefs,
      last: lastRefs,
      inputs,
      addButton,
      odoInput,
      odoButton,
      fillNodes,
      tables,
      toggles,
      rolling: { section: rollingSection, window: rollingWindow, fields: rollingFields },
      exportButton,
    };
    this._update(vehicle);
  }

  _update(vehicle) {
    const refs = this._refs;
    const currency = this._currency(vehicle);
    this._renderError();

    for (const [key, ref] of Object.entries(refs.values)) {
      const state = this._entity(vehicle, key);
      ref.amount.textContent = this._value(state, ref.stat.digits, ref.stat.money ? currency : null);
      ref.unit.textContent = ref.stat.money ? "" : this._unit(state);
      if (ref.chip) {
        const stamp = (state && state.attributes && state.attributes[ref.stat.period]) || "";
        ref.chip.textContent = stamp ? this._periodLabel(stamp) : "";
      }
    }

    // Glow header: identity, avatar (photo or car icon) and the headline number.
    const fillCount = this._value(this._entity(vehicle, "fill_count"), 0, null);
    refs.glow.name.textContent = vehicle.name;
    refs.glow.sub.textContent = [vehicle.fuelType, vehicle.engine, `${fillCount} fill-ups`]
      .filter(Boolean)
      .join(" · ");
    const image = this._image(vehicle);
    refs.glow.avatarImg.hidden = !image;
    refs.glow.avatarLetter.hidden = Boolean(image);
    if (image) refs.glow.avatarImg.src = image;

    const bigState = this._entity(vehicle, BIG.key);
    refs.big.amount.textContent = this._value(bigState, BIG.digits, null);
    refs.big.unit.textContent = this._unit(bigState);

    const history = this._history(vehicle);
    this._drawBars(refs.spark, history);
    const current = Number(bigState && bigState.state);
    const mean = history.length
      ? history.reduce((sum, row) => sum + row.avg_consumption, 0) / history.length
      : null;
    if (Number.isFinite(current) && mean) {
      const change = ((current - mean) / mean) * 100;
      refs.big.delta.textContent = `${change > 0 ? "+" : ""}${this._number(change, 1)}% vs 12-month`;
      refs.big.delta.className = `big-delta ${change > 0.5 ? "up" : change < -0.5 ? "down" : ""}`;
    } else {
      refs.big.delta.textContent = "";
      refs.big.delta.className = "big-delta";
    }

    // Period cards: the bar is this period's cost against the usual one.
    const rollingCost = Number(this._entity(vehicle, "rolling_cost")?.state);
    for (const panel of PERIOD_PANELS) {
      const cost = Number(this._entity(vehicle, panel.cost.key)?.state);
      const base = panel.cost.period === "month" ? rollingCost / 12 : rollingCost;
      const share = Number.isFinite(cost) && base > 0 ? Math.min(100, (cost / base) * 100) : 0;
      const progress = refs.panels[panel.cost.key];
      progress.fill.style.strokeDashoffset = String((2 * Math.PI * 15 * (1 - share / 100)).toFixed(2));
      progress.label.textContent = share ? `${Math.round(share)}%` : "";
    }

    this._renderHistory(vehicle);

    const last = this._entity(vehicle, "last_fill");
    const attrs = (last && last.attributes) || {};
    const tank = attrs.full === true ? "Full" : attrs.full === false ? "Partial" : "-";
    const setLast = (key, value) => {
      refs.last[key].textContent = value === null || value === undefined || value === "" ? "-" : value;
    };
    setLast("date", last && last.state && last.state !== "unknown" ? this._date(last.state) : "-");
    setLast("liters", Number.isFinite(attrs.liters) ? `${this._number(attrs.liters, 2)} L` : "-");
    setLast("price", Number.isFinite(attrs.price) ? this._money(attrs.price, currency) : "-");
    setLast("price_per_liter", Number.isFinite(attrs.price_per_liter)
      ? `${this._money(attrs.price_per_liter, currency)}/L`
      : "-");
    setLast("odometer", Number.isFinite(attrs.odometer) ? `${this._number(attrs.odometer, 1)} km` : "-");
    setLast("station", attrs.station);
    setLast("tank", tank);
    setLast("notes", attrs.notes);

    this._renderFills(vehicle, currency);
    this._renderRolling(vehicle, currency);
    for (const table of PERIOD_TABLES) this._renderPeriodTable(vehicle, currency, table);
  }

  /**
   * Trailing-window strip: the four rolling_* values plus the window label taken
   * from their `window` attribute. Hidden when no rolling sensor exists.
   */
  _renderRolling(vehicle, currency) {
    const refs = this._refs.rolling;
    let window = "";
    let present = false;
    for (const item of ROLLING) {
      const state = this._entity(vehicle, item.key);
      if (state) present = true;
      const attrs = (state && state.attributes) || {};
      if (!window && attrs.window) window = String(attrs.window);
      const text = [
        this._value(state, item.digits, item.money ? currency : null),
        item.money ? "" : this._unit(state),
      ]
        .filter(Boolean)
        .join(" ");
      refs.fields[item.key].textContent = text;
    }
    refs.window.textContent = window;
    refs.window.hidden = !window;
    refs.section.hidden = !present;
  }

  /**
   * Section head carrying the shared "Show all (N)"/"Show less" toggle.
   * `key` names the collapsible list; the toggle lands in `toggles[key]`.
   * A list without a collapsed row count gets a plain head instead.
   */
  _showAllHead(key, title, toggles, collapsible = true) {
    const head = el("div", { class: "section-head" }, [el("span", { text: title })]);
    if (!collapsible) return head;
    const toggle = el("button", {
      class: "link",
      type: "button",
      text: "Show all",
      onclick: () => this._toggle(key),
    });
    toggles[key] = toggle;
    head.append(toggle);
    return head;
  }

  /**
   * Sync the toggle for `key` and return how many rows to render: all of them
   * when expanded, otherwise `collapsed`. The toggle hides itself when there is
   * nothing collapsed.
   */
  _showAllRows(key, total, collapsed) {
    const toggle = this._refs.toggles[key];
    const expanded = !!this._showAll[key];
    toggle.hidden = total <= collapsed;
    toggle.textContent = expanded ? "Show less" : `Show all (${total})`;
    return expanded ? total : collapsed;
  }

  _renderFills(vehicle, currency) {
    const fills = this._fillups(vehicle);
    const nodes = this._refs.fillNodes;
    const limit = this._showAllRows("fills", fills.length, 5);
    this._displayedFills = Math.min(limit, fills.length);
    nodes.innerHTML = "";

    if (!fills.length) {
      nodes.append(el("div", { class: "empty", text: "No fill-ups recorded yet." }));
      return;
    }

    for (const fill of fills.slice(0, limit)) {
      const perLiter = Number(fill.liters) ? Number(fill.price) / Number(fill.liters) : null;
      const main = `${this._number(Number(fill.liters), 2)} L · ${this._money(Number(fill.price), currency)}`;
      const meta = [
        this._date(fill.date),
        Number.isFinite(Number(fill.odometer)) && fill.odometer !== null
          ? `${this._number(Number(fill.odometer), 1)} km`
          : null,
        fill.station,
        fill.full === false ? "partial" : null,
        Number.isFinite(perLiter) ? `${this._money(perLiter, currency)}/L` : null,
        fill.notes,
      ]
        .filter(Boolean)
        .join(" · ");
      // Leg keys only exist on a full fill-up that closed a measured leg.
      const leg = [
        fill.leg_distance === null || fill.leg_distance === undefined
          ? null
          : `${this._number(Number(fill.leg_distance), 0)} km`,
        fill.leg_liters === null || fill.leg_liters === undefined
          ? null
          : `${this._number(Number(fill.leg_liters), 2)} L`,
        fill.leg_consumption === null || fill.leg_consumption === undefined
          ? null
          : `${this._number(Number(fill.leg_consumption), 2)} L/100km`,
        fill.leg_cost === null || fill.leg_cost === undefined
          ? null
          : this._money(Number(fill.leg_cost), currency),
      ]
        .filter(Boolean)
        .join(" · ");

      const row = [
        el("div", { class: "main", text: main }),
        el("div", { class: "meta", text: meta }),
      ];
      if (leg) row.push(el("div", { class: "leg", text: `Leg: ${leg}` }));
      row.push(
        el("button", {
          class: "danger",
          type: "button",
          text: "Delete",
          onclick: () => this._deleteFillup(fill.id),
        })
      );
      nodes.append(el("div", { class: "fill" }, row));
    }
  }

  /** Signed percentage change of `current` against the older month's value. */
  _delta(current, previous) {
    if (current === null || current === undefined) return "-";
    if (previous === null || previous === undefined) return "-";
    const value = Number(current);
    const base = Number(previous);
    if (!Number.isFinite(value) || !Number.isFinite(base) || base === 0) return "-";
    const pct = ((value - base) / base) * 100;
    const sign = pct > 0 ? "+" : pct < 0 ? "-" : "";
    return `${sign}${this._number(Math.abs(pct), 1)}%`;
  }

  /** `2026-03` -> localized short month + year ("Mär 2026"); `2026` stays as is. */
  _periodLabel(period) {
    const text = String(period || "");
    const match = /^(\d{4})-(\d{2})$/.exec(text);
    if (!match) return text || "-";
    const date = new Date(Number(match[1]), Number(match[2]) - 1, 1);
    try {
      return new Intl.DateTimeFormat(this._locale(), {
        month: "short",
        year: "numeric",
      }).format(date);
    } catch (err) {
      return text;
    }
  }

  /** One comparison table; `table` is an entry of PERIOD_TABLES. */
  _renderPeriodTable(vehicle, currency, table) {
    const container = this._refs.tables[table.toggle];
    container.innerHTML = "";
    const state = this._entity(vehicle, table.entity);
    const attrs = (state && state.attributes) || {};
    const rows = Array.isArray(attrs[table.rows]) ? attrs[table.rows] : [];
    const current = attrs[table.current] || null;
    const limit = table.limit
      ? this._showAllRows(table.toggle, rows.length, table.limit)
      : rows.length;

    if (!rows.length) {
      container.append(el("div", { class: "empty", text: table.empty }));
      return;
    }

    const num = (value, digits, suffix = "") =>
      value === null || value === undefined || !Number.isFinite(Number(value))
        ? "-"
        : `${this._number(Number(value), digits)}${suffix}`;
    const money = (value) =>
      value === null || value === undefined || !Number.isFinite(Number(value))
        ? "-"
        : this._money(Number(value), currency);
    const cell = (text, delta) =>
      el("td", {}, [
        el("div", { text }),
        delta === null ? null : el("div", { class: "delta", text: delta }),
      ]);

    const head = el("tr", {}, [
      el("th", { scope: "col", text: table.header }),
      el("th", { scope: "col", text: "km" }),
      el("th", { scope: "col", text: "L" }),
      el("th", { scope: "col", text: "Cost" }),
      el("th", { scope: "col", text: "L/100km" }),
      el("th", { scope: "col", text: "Fills" }),
    ]);
    const body = el("tbody");
    for (const [index, row] of rows.slice(0, limit).entries()) {
      const older = rows[index + 1];
      const isCurrent = current !== null && row.period === current;
      body.append(
        el("tr", { class: isCurrent ? "current" : null }, [
          el("td", { class: "period" }, [
            el("span", { class: "period-label", text: this._periodLabel(row.period) }),
            isCurrent ? el("span", { class: "now", text: "current" }) : null,
          ]),
          cell(num(row.distance, 0, " km"), this._delta(row.distance, older && older.distance)),
          cell(num(row.liters, 1), null),
          cell(money(row.cost), this._delta(row.cost, older && older.cost)),
          cell(num(row.avg_consumption, 2), this._delta(row.avg_consumption, older && older.avg_consumption)),
          cell(num(row.fill_count, 0), null),
        ])
      );
    }
    container.append(
      el("table", { class: "periods-table" }, [el("thead", {}, [head]), body])
    );
  }

  _renderError() {
    const error = this._refs && this._refs.error;
    if (!error) return;
    error.textContent = this._error || "";
    error.className = this._errorIsNotice ? "notice" : "error";
    if (this._error) error.removeAttribute("hidden");
    else error.setAttribute("hidden", "");
  }

  _setError(message) {
    this._errorIsNotice = false;
    this._trendIndex = 0;
    this._trendPick = null;
    this._trendRows = [];
    this._trendRange = 12;
    this._error = message || null;
    this._renderError();
  }

  /** Success text shares the card's single message line with errors. */
  _setNotice(message) {
    this._errorIsNotice = true;
    this._error = message || null;
    this._renderError();
  }

  _selectVehicle(id) {
    this._selected = id;
    try {
      window.localStorage.setItem("fuelusagetracker.vehicle", id);
    } catch (err) {
      // Private mode / blocked storage: the picker just does not persist.
    }
    this._render();
  }

  _toggle(key) {
    this._showAll[key] = !this._showAll[key];
    const vehicle = this._vehicle();
    if (!vehicle) return;
    const currency = this._currency(vehicle);
    if (key === "fills") this._renderFills(vehicle, currency);
    else this._renderPeriodTable(vehicle, currency, PERIOD_TABLES.find((table) => table.toggle === key));
  }

  // --- actions ------------------------------------------------------------

  async _callService(service, data) {
    this._setError(null);
    this._busy = true;
    try {
      await this._hass.callService(DOMAIN, service, data);
      return true;
    } catch (err) {
      this._setError((err && err.message) || `${service} failed`);
      return false;
    } finally {
      this._busy = false;
    }
  }

  /**
   * `export_csv` with `returnResponse` (a positional flag on `hass.callService`)
   * so the card can report the written path; the notice area shows one line.
   */
  async _exportCsv() {
    const vehicle = this._vehicle();
    if (!vehicle || this._busy) return;
    this._busy = true;
    this._setError(null);
    try {
      const response = await this._hass.callService(
        DOMAIN,
        "export_csv",
        { vehicle: vehicle.id, scope: "fillups" },
        undefined,
        false,
        true
      );
      const result = (response && response.response) || response || {};
      if (result.path) this._setNotice(`Exported ${result.rows} rows to ${result.path}`);
      else this._setError("CSV export returned no path.");
    } catch (err) {
      this._setError((err && err.message) || "export_csv failed");
    } finally {
      this._busy = false;
    }
  }

  async _addFillup() {
    const vehicle = this._vehicle();
    const inputs = this._refs.inputs;
    if (!vehicle || this._busy) return;

    const liters = parseFloat(inputs.liters.value);
    const price = parseFloat(inputs.price.value);
    if (!Number.isFinite(liters) || liters <= 0) {
      this._setError("Enter the number of litres (greater than 0).");
      return;
    }
    if (!Number.isFinite(price) || price < 0) {
      this._setError("Enter the total price paid.");
      return;
    }

    const data = { vehicle: vehicle.id, liters, price, full: inputs.full.checked };
    const odometer = parseFloat(inputs.odometer.value);
    if (Number.isFinite(odometer) && odometer >= 0) data.odometer = odometer;
    if (inputs.station.value.trim()) data.station = inputs.station.value.trim();
    if (inputs.date.value) {
      const date = new Date(inputs.date.value);
      if (!Number.isNaN(date.getTime())) data.date = date.toISOString();
    }

    if (await this._callService("add_fillup", data)) {
      inputs.liters.value = "";
      inputs.price.value = "";
      inputs.odometer.value = "";
      inputs.station.value = "";
      inputs.date.value = this._localDatetime();
      inputs.liters.focus();
    }
  }

  async _updateOdometer() {
    const vehicle = this._vehicle();
    const refs = this._refs;
    if (!vehicle || this._busy) return;
    const odometer = parseFloat(refs.odoInput.value);
    if (!Number.isFinite(odometer) || odometer < 0) {
      this._setError("Enter the current odometer reading in km.");
      return;
    }
    const saved = await this._callService("update_vehicle", {
      vehicle: vehicle.id,
      odometer,
    });
    if (saved) {
      refs.odoInput.value = "";
      refs.odoInput.blur();
    }
  }

  async _deleteFillup(fillupId) {
    const vehicle = this._vehicle();
    if (!vehicle || !fillupId) return;
    const fill = this._fillups(vehicle).find((item) => item.id === fillupId);
    const label = fill
      ? `${this._number(Number(fill.liters), 2)} L on ${this._date(fill.date)}`
      : "this fill-up";
    if (!window.confirm(`Delete ${label}? This cannot be undone.`)) return;
    await this._callService("delete_fillup", {
      vehicle: vehicle.id,
      fillup_id: fillupId,
    });
  }
}

/**
 * Group tracked entities by vehicle (config entry id) using only the identity
 * attributes; returns [{id, name, fuelType, engine, keys: {key: entity_id}}].
 */
function discoverVehicles(hass) {
  const vehicles = new Map();
  if (!hass || !hass.states) return [];
  for (const state of Object.values(hass.states)) {
    const attributes = state.attributes || {};
    if (
      typeof attributes.key !== "string" ||
      typeof attributes.vehicle !== "string" ||
      typeof attributes.vehicle_name !== "string"
    ) {
      continue;
    }
    let vehicle = vehicles.get(attributes.vehicle);
    if (!vehicle) {
      vehicle = {
        id: attributes.vehicle,
        name: attributes.vehicle_name,
        fuelType: attributes.fuel_type || "",
        engine: attributes.engine || "",
        keys: {},
      };
      vehicles.set(attributes.vehicle, vehicle);
    }
    if (!vehicle.keys[attributes.key]) vehicle.keys[attributes.key] = state.entity_id;
  }
  return [...vehicles.values()];
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, FuelUsageTrackerCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Fuel Usage Tracker",
    description:
      "Refuelling summary and fill-up log for a vehicle tracked by Fuel Usage Tracker.",
    preview: true,
  });
}
