/**
 * Fuel Usage Tracker card — vanilla JS, no build step.
 *
 * Everything is discovered from state attributes (key / vehicle / vehicle_name /
 * fuel_type / engine), never from guessed entity ids, so renamed entities keep
 * working. Fill-ups come from the `fillups` attribute of the `last_fill` entity;
 * writes go through the fuelusagetracker services.
 */

const CARD_TAG = "fuelusagetracker-card";
const DOMAIN = "fuelusagetracker";

/** Summary tiles: attribute key, label, fraction digits, monetary flag. */
const STATS = [
  { key: "avg_consumption", label: "Avg consumption", digits: 2 },
  { key: "last_consumption", label: "Last consumption", digits: 2 },
  { key: "cost_per_km", label: "Cost per km", digits: 3 },
  // Not money: the unit span carries the per-litre unit (e.g. "EUR/L"), like cost_per_km.
  { key: "avg_price_per_liter", label: "Avg price per litre", digits: 3 },
  { key: "total_cost", label: "Total cost", digits: 2, money: true },
  { key: "total_liters", label: "Total litres", digits: 2 },
  { key: "total_distance", label: "Total distance", digits: 0 },
  { key: "km_since_last_fill", label: "Km since last fill", digits: 0 },
  { key: "fill_count", label: "Fill-ups", digits: 0 },
];

const STYLES = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .header { display: flex; align-items: center; gap: 12px; padding: 12px 16px 0; flex-wrap: wrap; }
  .header .name { flex: 1 1 auto; font-size: 1.15rem; font-weight: 500; color: var(--primary-text-color); }
  .header select { max-width: 100%; }
  .sub { padding: 2px 16px 10px; font-size: .85rem; color: var(--secondary-text-color); }
  .sub:empty { display: none; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(96px, 1fr)); gap: 8px; padding: 0 16px 12px; }
  .stat { padding: 8px 10px; border-radius: 8px; background: var(--secondary-background-color); }
  .stat .label { font-size: .72rem; letter-spacing: .04em; text-transform: uppercase; color: var(--secondary-text-color); }
  .stat .value { margin-top: 2px; font-size: 1.05rem; color: var(--primary-text-color); }
  .stat .unit { margin-left: 3px; font-size: .72rem; color: var(--secondary-text-color); }
  .section { border-top: 1px solid var(--divider-color); }
  .section-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 10px 16px 6px; font-weight: 500; color: var(--primary-text-color); }
  .rows, form.grid, .actions, .fills { padding: 0 16px 12px; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 2px 0; font-size: .9rem; color: var(--primary-text-color); }
  .row .k { color: var(--secondary-text-color); }
  .row .v { text-align: right; }
  form.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 8px; align-items: end; }
  .field { display: flex; flex-direction: column; gap: 3px; font-size: .75rem; color: var(--secondary-text-color); }
  .field.check { flex-direction: row; align-items: center; gap: 6px; padding-bottom: 7px; font-size: .85rem; }
  input, select { box-sizing: border-box; min-width: 0; width: 100%; padding: 6px 8px; font: inherit; color: var(--primary-text-color); background: var(--card-background-color); border: 1px solid var(--divider-color); border-radius: 6px; }
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
  .fill .meta { grid-column: 1; font-size: .78rem; color: var(--secondary-text-color); }
  .fill button { grid-area: 1 / 2 / span 2 / 3; align-self: center; }
  .empty, .error { padding: 0 16px 12px; font-size: .85rem; }
  .empty { color: var(--secondary-text-color); }
  .error { color: var(--error-color, #db4437); }
  .error[hidden] { display: none; }
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

class FuelUsageTrackerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._built = false;
    this._selected = null;
    this._showAllFills = false;
    this._busy = false;
    this._error = null;
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
    return 6 + Math.min(4, this._displayedFills || 0);
  }

  // --- data discovery ------------------------------------------------------

  _discover() {
    return discoverVehicles(this._hass);
  }

  _vehicle() {
    return this._discover().find((vehicle) => vehicle.id === this._vehId);
  }

  _currentVehicle(vehicles) {
    const config = this._config || {};
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
    for (const key of ["total_cost", "last_fill_cost", "cost_per_km", "avg_price_per_liter"]) {
      const state = this._entity(vehicle, key);
      const unit = state && state.attributes && state.attributes.unit_of_measurement;
      if (unit) return String(unit).split("/")[0].trim();
    }
    return (this._hass.config && this._hass.config.currency) || "";
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
    if (!this._built) {
      this._render();
      return;
    }
    const vehicle = this._vehicle();
    const current = this._currentVehicle(this._discover());
    if (!vehicle || !current || current.id !== vehicle.id) this._render();
    else this._update(vehicle);
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

    // Header: vehicle name and a picker when there is more than one vehicle.
    const header = el("div", { class: "header" }, [
      el("span", { class: "name", text: vehicle.name }),
    ]);
    if (vehicles.length > 1) {
      const select = el(
        "select",
        { "aria-label": "Vehicle", onchange: (event) => this._selectVehicle(event.target.value) },
        vehicles.map((item) =>
          el("option", { value: item.id, text: item.name, selected: item.id === vehicle.id ? "" : null })
        )
      );
      header.append(select);
    }
    const subtitle = el("div", { class: "sub" });
    const error = el("div", { class: "error", hidden: "" });
    card.append(header, subtitle, error);

    // Summary tiles.
    const stats = el("div", { class: "stats" });
    const statRefs = {};
    for (const stat of STATS) {
      const amount = el("span");
      const unit = el("span", { class: "unit" });
      const value = el("div", { class: "value" }, [amount, unit]);
      stats.append(
        el("div", { class: "stat" }, [el("div", { class: "label", text: stat.label }), value])
      );
      statRefs[stat.key] = { amount, unit, stat };
    }
    card.append(stats);

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

    // Odometer update.
    const odoInput = el("input", { type: "number", min: "0", step: "1", inputmode: "decimal", placeholder: "km" });
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
      liters: el("input", { type: "number", min: "0.001", step: "0.01", inputmode: "decimal", required: "" }),
      price: el("input", { type: "number", min: "0", step: "0.01", inputmode: "decimal", required: "" }),
      odometer: el("input", { type: "number", min: "0", step: "1", inputmode: "decimal" }),
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

    // Recent fill-ups.
    const fillNodes = el("div", { class: "fills" });
    const showAllButton = el("button", {
      class: "link",
      type: "button",
      text: "Show all",
      onclick: () => this._toggleFills(),
    });
    card.append(
      el("div", { class: "section" }, [
        el("div", { class: "section-head" }, [
          el("span", { text: "Recent fill-ups" }),
          showAllButton,
        ]),
        fillNodes,
      ])
    );

    this._refs = {
      subtitle,
      error,
      stats: statRefs,
      last: lastRefs,
      inputs,
      addButton,
      odoInput,
      odoButton,
      fillNodes,
      showAllButton,
    };
    this._update(vehicle);
  }

  _update(vehicle) {
    const refs = this._refs;
    const currency = this._currency(vehicle);
    const fuel = vehicle.fuelType;
    const engine = vehicle.engine;
    refs.subtitle.textContent = [fuel, engine].filter(Boolean).join(" · ");
    this._renderError();

    for (const [key, ref] of Object.entries(refs.stats)) {
      const state = this._entity(vehicle, key);
      ref.amount.textContent = this._value(state, ref.stat.digits, ref.stat.money ? currency : null);
      ref.unit.textContent = ref.stat.money ? "" : this._unit(state);
    }

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
  }

  _renderFills(vehicle, currency) {
    const fills = this._fillups(vehicle);
    const nodes = this._refs.fillNodes;
    const limit = this._showAllFills ? fills.length : 5;
    this._displayedFills = Math.min(limit, fills.length);
    nodes.innerHTML = "";
    this._refs.showAllButton.hidden = fills.length <= 5;
    this._refs.showAllButton.textContent = this._showAllFills
      ? "Show less"
      : `Show all (${fills.length})`;

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

      nodes.append(
        el("div", { class: "fill" }, [
          el("div", { class: "main", text: main }),
          el("div", { class: "meta", text: meta }),
          el("button", {
            class: "danger",
            type: "button",
            text: "Delete",
            onclick: () => this._deleteFillup(fill.id),
          }),
        ])
      );
    }
  }

  _renderError() {
    const error = this._refs && this._refs.error;
    if (!error) return;
    error.textContent = this._error || "";
    if (this._error) error.removeAttribute("hidden");
    else error.setAttribute("hidden", "");
  }

  _setError(message) {
    this._error = message || null;
    this._renderError();
  }

  _selectVehicle(id) {
    this._selected = id;
    this._render();
  }

  _toggleFills() {
    this._showAllFills = !this._showAllFills;
    const vehicle = this._vehicle();
    if (vehicle) this._renderFills(vehicle, this._currency(vehicle));
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
