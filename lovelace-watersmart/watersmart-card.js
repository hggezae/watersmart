/**
 * WaterSmart Card — Lovelace card for the WaterSmart integration.
 *
 * Renders an hourly usage bar chart (utility-reported leak hours highlighted)
 * and a GitHub-contribution-style daily heatmap from the
 * `watersmart.get_hourly_history` service response.
 *
 * Zero dependencies, no build step. Reference this file directly as a
 * Lovelace resource, e.g. `/local/watersmart-card.js`.
 *
 * Example config:
 *
 * ```yaml
 * type: custom:watersmart-card
 * title: Water usage
 * # entry: 1b4a46c6cba0677bbfb5a8c53e8618b0   # optional unless you have
 *                                              # multiple WaterSmart accounts
 * hours: 48                                    # hourly bar chart depth
 * weeks: 12                                    # heatmap depth
 * ```
 */

const GALLONS_PER_LITER = 3.785411784;
const REFRESH_INTERVAL_MS = 10 * 60 * 1000;

/* eslint-disable no-console */
const log = (...args) => console.log("watersmart-card:", ...args);


class WatersmartCard extends HTMLElement {
  /** Default configuration. */
  static DEFAULTS = Object.freeze({
    title: "",
    entry: "",
    hours: 48,
    weeks: 12,
    unit: "auto",
  });

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = { ...WatersmartCard.DEFAULTS };
    this._hass = null;
    /** @type {Array<{date: Date, gallons: number, leakGallons: number}>|null} */
    this._records = null;
    this._error = null;
    this._loading = false;
    this._refreshTimer = null;
  }

  setConfig(config) {
    if (!config || typeof config !== "object") {
      throw new Error("watersmart-card: config must be an object");
    }
    const merged = { ...WatersmartCard.DEFAULTS, ...config };
    const errors = [];
    if (merged.entry != null && typeof merged.entry !== "string") {
      errors.push("`entry` must be a string");
    }
    if (!Number.isFinite(Number(merged.hours)) || Number(merged.hours) < 1) {
      errors.push("`hours` must be a positive number");
    }
    if (!Number.isFinite(Number(merged.weeks)) || Number(merged.weeks) < 1) {
      errors.push("`weeks` must be a positive number");
    }
    if (!["auto", "gal", "L"].includes(merged.unit)) {
      errors.push("`unit` must be one of: auto, gal, L");
    }
    if (errors.length) throw new Error(`watersmart-card: ${errors.join("; ")}`);

    this._config = {
      ...merged,
      hours: Math.min(Math.round(Number(merged.hours)), 24 * 14),
      weeks: Math.min(Math.round(Number(merged.weeks)), 26),
    };
    // A new config may point at a different entry: drop cached data.
    this._records = null;
    this._error = null;
    if (this.isConnected) this._scheduleFetch();
    this.render();
  }

  set hass(hass) {
    const firstRun = this._hass === null;
    this._hass = hass;
    if (firstRun || !this._records) {
      this.render();
      this._scheduleFetch();
    } else {
      // Unit system may have changed; re-render with existing data.
      this.render();
    }
  }

  getCardSize() {
    return 5;
  }

  static getStubConfig() {
    return { type: "custom:watersmart-card", hours: 48, weeks: 12 };
  }

  disconnectedCallback() {
    if (this._refreshTimer) clearTimeout(this._refreshTimer);
    this._refreshTimer = null;
  }

  connectedCallback() {
    if (!this._refreshTimer) this._scheduleFetch();
  }

  _scheduleFetch() {
    if (this._refreshTimer) clearTimeout(this._refreshTimer);
    this._fetchData();
    this._refreshTimer = setTimeout(() => {
      this._refreshTimer = null;
      if (this.isConnected) this._scheduleFetch();
    }, REFRESH_INTERVAL_MS);
  }

  async _resolveEntryId() {
    if (this._config.entry) return this._config.entry;
    const entries = await this._hass.connection.sendMessagePromise({
      type: "config_entries/get",
      domain: "watersmart",
    });
    const usable = entries.filter((entry) => !entry.disabled_by);
    if (usable.length === 0) {
      throw new Error("No WaterSmart config entries found.");
    }
    if (usable.length > 1) {
      throw new Error(
        "Multiple WaterSmart accounts found. Add `entry:` to the card config " +
          "with one of: " +
          usable.map((entry) => `${entry.title} (${entry.entry_id})`).join(", "),
      );
    }
    return usable[0].entry_id;
  }

  async _fetchData() {
    if (!this._hass || this._loading) return;
    this._loading = true;
    this._error = null;
    try {
      const entryId = await this._resolveEntryId();
      const result = await this._hass.connection.sendMessagePromise({
        type: "call_service",
        domain: "watersmart",
        service: "get_hourly_history",
        return_response: true,
        data: { config_entry: entryId, cached: true },
      });
      const history = result?.response?.history ?? [];
      this._records = history.map((record) => ({
        date: new Date(record.start),
        gallons: Number(record.gallons) || 0,
        leakGallons: Number(record.leak_gallons) || 0,
      }));
      // Service returns ascending order already; sort defensively for charts.
      this._records.sort((a, b) => a.date - b.date);
    } catch (err) {
      this._error = err?.message ?? String(err);
      log("failed to load history", err);
    } finally {
      this._loading = false;
      this.render();
    }
  }

  _displayUnit() {
    if (this._config.unit !== "auto") return this._config.unit;
    const volumeUnit = this._hass?.config?.unit_system?.volume_unit;
    return String(volumeUnit || "gal").toLowerCase().startsWith("l") ? "L" : "gal";
  }

  _convert(gallons) {
    return this._displayUnit() === "L" ? gallons * GALLONS_PER_LITER : gallons;
  }

  _format(value) {
    const rounded = Math.round(value * 10) / 10;
    return rounded.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }

  render() {
    const style = document.createElement("style");
    style.textContent = `
      ha-card { padding: 16px; display: block; }
      .header { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 12px; }
      .title { font-size: 1.2em; font-weight: 500; color: var(--primary-text-color); }
      .summary { font-size: 0.9em; color: var(--secondary-text-color); }
      .bars { display: flex; align-items: flex-end; gap: 2px; height: 90px; }
      .bar { flex: 1 1 0; min-width: 1px; border-radius: 2px 2px 0 0;
             background: rgb(var(--rgb-primary-color, 3, 169, 244)); opacity: 0.75; position: relative; }
      .bar.zero { opacity: 0.15; }
      .bar.leak { background: var(--label-red-background, #f44336); opacity: 0.95; }
      .axis { display: flex; justify-content: space-between; font-size: 0.7em;
              color: var(--secondary-text-color); margin-top: 4px; }
      .heatmap { display: grid; grid-auto-flow: column; grid-template-rows: repeat(7, 1fr);
                 gap: 3px; margin-top: 16px; }
      .cell { width: 13px; height: 13px; border-radius: 3px; background: var(--divider-color, #444); opacity: 0.25; }
      .cell.empty { visibility: hidden; }
      .cell.l0 { opacity: 0.25; }
      .cell.l1 { background: var(--rgb-primary-color, 3, 169, 244); opacity: 0.35; }
      .cell.l2 { background: var(--rgb-primary-color, 3, 169, 244); opacity: 0.55; }
      .cell.l3 { background: var(--rgb-primary-color, 3, 169, 244); opacity: 0.75; }
      .cell.l4 { background: var(--rgb-primary-color, 3, 169, 244); opacity: 0.95; }
      .cell.leak { box-shadow: inset 0 0 0 2px var(--label-red-background, #f44336); }
      .legend { display: flex; align-items: center; gap: 8px; margin-top: 10px;
                font-size: 0.75em; color: var(--secondary-text-color); }
      .legend .swatch { width: 11px; height: 11px; border-radius: 3px; display: inline-block; }
      .legend .leak-swatch { background: var(--label-red-background, #f44336); }
      .message { padding: 12px 0; color: var(--secondary-text-color); }
      .error { color: var(--error-color, #db4437); }
      button.retry { margin-top: 8px; cursor: pointer; }
    `;
    this.shadowRoot.innerHTML = "";
    this.shadowRoot.append(style, this._buildCard());
  }

  _buildCard() {
    const card = document.createElement("ha-card");

    if (this._error) {
      card.innerHTML = `
        <div class="header"><span class="title">${this._escape(this._cardTitle())}</span></div>
        <div class="message error">${this._escape(this._error)}</div>
        <button class="retry">Retry</button>`;
      card.querySelector("button.retry").addEventListener("click", () => {
        this._error = null;
        this.render();
        this._fetchData();
      });
      return card;
    }

    if (this._loading && !this._records) {
      card.innerHTML = `
        <div class="header"><span class="title">${this._escape(this._cardTitle())}</span></div>
        <div class="message">Loading water usage…</div>`;
      return card;
    }

    if (!this._records || this._records.length === 0) {
      card.innerHTML = `
        <div class="header"><span class="title">${this._escape(this._cardTitle())}</span></div>
        <div class="message">No water usage data available.</div>`;
      return card;
    }

    const unit = this._displayUnit();
    const last = this._records[this._records.length - 1];
    const dayTotal = this._sumDay(last.date);

    card.innerHTML = `
      <div class="header">
        <span class="title">${this._escape(this._cardTitle())}</span>
        <span class="summary">Last day: ${this._format(this._convert(dayTotal))} ${unit}</span>
      </div>
      <div class="bars"></div>
      <div class="axis">
        <span>${this._timeLabel(this._records[Math.max(0, this._records.length - this._config.hours)].date)}</span>
        <span>now</span>
      </div>
      <div class="heatmap"></div>
      <div class="legend">
        <span class="swatch leak-swatch"></span><span>Leak reported by utility</span>
      </div>`;

    this._renderBars(card.querySelector(".bars"));
    this._renderHeatmap(card.querySelector(".heatmap"));
    return card;
  }

  _cardTitle() {
    return this._config.title || "Water usage";
  }

  _renderBars(container) {
    const slice = this._records.slice(-this._config.hours);
    const peak = Math.max(...slice.map((r) => r.gallons + r.leakGallons), 0.001);
    for (const record of slice) {
      const total = record.gallons + record.leakGallons;
      const bar = document.createElement("div");
      bar.className = "bar";
      if (record.leakGallons > 0) bar.classList.add("leak");
      if (total === 0) bar.classList.add("zero");
      bar.style.height = `${Math.max((total / peak) * 100, total > 0 ? 2 : 0)}%`;
      const unit = this._displayUnit();
      bar.title =
        `${record.date.toLocaleString()} — ${this._format(this._convert(total))} ${unit}` +
        (record.leakGallons > 0
          ? ` (includes ${this._format(this._convert(record.leakGallons))} ${unit} leak)`
          : "");
      container.append(bar);
    }
  }

  _renderHeatmap(container) {
    const days = this._groupByDay();
    const today = this._dayKey(new Date());
    // Align the grid so its last column ends on Saturday (rows Mon..Sun).
    const lastDate = days.length ? days[days.length - 1].date : new Date(today);
    const leadingBlanks = (lastDate.getDay() + 6) % 7;
    for (let i = 0; i < leadingBlanks; i++) {
      const pad = document.createElement("div");
      pad.className = "cell empty";
      container.append(pad);
    }
    const cutoff = new Date(today);
    cutoff.setDate(cutoff.getDate() - this._config.weeks * 7);
    for (const day of days) {
      if (day.date < cutoff) continue;
      const cell = document.createElement("div");
      const level = this._level(day.total, days);
      cell.className = `cell l${level}`;
      if (day.leak) cell.classList.add("leak");
      const unit = this._displayUnit();
      cell.title = `${day.date.toLocaleDateString()} — ${this._format(this._convert(day.total))} ${unit}` +
        (day.leak ? " (leak reported)" : "");
      container.append(cell);
    }
  }

  _level(total, days) {
    if (total <= 0) return 0;
    const sorted = days.map((d) => d.total).filter((t) => t > 0).sort((a, b) => a - b);
    const pick = (p) => sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * p))];
    if (total <= pick(0.25)) return 1;
    if (total <= pick(0.5)) return 2;
    if (total <= pick(0.75)) return 3;
    return 4;
  }

  _groupByDay() {
    const map = new Map();
    for (const record of this._records) {
      const key = this._dayKey(record.date);
      const day =
        map.get(key) ??
        ({ date: new Date(record.date.getFullYear(), record.date.getMonth(), record.date.getDate()), total: 0, leak: false });
      day.total += record.gallons + record.leakGallons;
      day.leak ||= record.leakGallons > 0;
      map.set(key, day);
    }
    return [...map.values()];
  }

  _dayKey(date) {
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  }

  _sumDay(date) {
    const key = this._dayKey(date);
    return this._records
      .filter((r) => this._dayKey(r.date) === key)
      .reduce((acc, r) => acc + r.gallons + r.leakGallons, 0);
  }

  _timeLabel(date) {
    return date.toLocaleTimeString(undefined, { hour: "numeric" });
  }

  _escape(text) {
    const div = document.createElement("div");
    div.textContent = String(text);
    return div.innerHTML;
  }
}

customElements.define("watersmart-card", WatersmartCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "watersmart-card",
  name: "WaterSmart Card",
  description: "Hourly water usage bars and daily heatmap for the WaterSmart integration.",
});

// Minimal visual editor: labeled inputs bound to the card config.
class WatersmartCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    if (!this.shadowRoot && this.isConnected) this._render();
  }

  connectedCallback() {
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this._render();
    }
  }

  _dispatchChange() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config }, bubbles: true, composed: true }));
  }

  _field(label, key, type) {
    const wrap = document.createElement("label");
    wrap.style.cssText = "display:block;font-size:.85em;margin-bottom:8px;";
    const span = document.createElement("span");
    span.textContent = `${label}: `;
    const input = document.createElement("input");
    input.type = type;
    input.value = this._config[key] ?? "";
    input.addEventListener("input", () => {
      this._config = { ...this._config, [key]: input.value };
      this._dispatchChange();
    });
    wrap.append(span, input);
    return wrap;
  }

  _render() {
    this.shadowRoot.innerHTML = "";
    this.shadowRoot.append(
      this._field("Title", "title", "text"),
      this._field("Entry ID (optional)", "entry", "text"),
      this._field("Hours of bars", "hours", "number"),
      this._field("Weeks of heatmap", "weeks", "number"),
    );
  }
}
customElements.define("watersmart-card-editor", WatersmartCardEditor);
WatersmartCard.getConfigElement = function () {
  return document.createElement("watersmart-card-editor");
};
