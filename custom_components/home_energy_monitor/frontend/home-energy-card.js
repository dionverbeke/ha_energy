/*
 * Home Energy Card — live energy-flow view for the Home Energy Monitor integration.
 * Served automatically by the integration; add it to a dashboard with:
 *   type: custom:home-energy-card
 */
const CARD_VERSION = "1.0.0";

// viewBox 500 x 360
const POS = {
  solar: [170, 60],
  grid: [55, 180],
  battery: [170, 295],
  home: [300, 180],
  heat_pump: [440, 70],
  ev: [440, 180],
  other: [440, 290],
};

const COLOR = {
  solar: "var(--energy-solar-color, #ff9800)",
  grid: "var(--energy-grid-consumption-color, #488fc2)",
  export: "var(--energy-grid-return-color, #8353d1)",
  battery: "var(--energy-battery-out-color, #4db6ac)",
  battery_in: "var(--energy-battery-in-color, #f06292)",
  home: "var(--primary-text-color, #212121)",
  heat_pump: "#e57373",
  ev: "#26a69a",
  other: "var(--secondary-text-color, #727272)",
};

// line id -> [from, to, color, requires]
const LINES = {
  solar_to_home: ["solar", "home", COLOR.solar, ["solar"]],
  solar_to_grid: ["solar", "grid", COLOR.export, ["solar"]],
  solar_to_battery: ["solar", "battery", COLOR.solar, ["solar", "battery"]],
  grid_to_home: ["grid", "home", COLOR.grid, []],
  grid_battery: ["grid", "battery", COLOR.grid, ["battery"]],
  battery_to_home: ["battery", "home", COLOR.battery, ["battery"]],
  home_to_heat_pump: ["home", "heat_pump", COLOR.heat_pump, ["heat_pump"]],
  home_to_ev: ["home", "ev", COLOR.ev, ["ev"]],
  home_to_other: ["home", "other", COLOR.other, []],
};

const NODES = {
  solar: { icon: "mdi:solar-power-variant", label: "Solar", color: COLOR.solar, requires: ["solar"] },
  grid: { icon: "mdi:transmission-tower", label: "Grid", color: COLOR.grid, requires: [] },
  battery: { icon: "mdi:battery-high", label: "Battery", color: COLOR.battery, requires: ["battery"] },
  home: { icon: "mdi:home", label: "Home", color: COLOR.home, requires: [], big: true },
  heat_pump: { icon: "mdi:heat-pump", label: "Heat pump", color: COLOR.heat_pump, requires: ["heat_pump"] },
  ev: { icon: "mdi:ev-station", label: "Car", color: COLOR.ev, requires: ["ev"] },
  other: { icon: "mdi:power-plug", label: "Other", color: COLOR.other, requires: [] },
};

const NL = {
  Solar: "Zon", Grid: "Net", Battery: "Batterij", Home: "Huis", "Heat pump": "Warmtepomp",
  Car: "Auto", Other: "Overig", import: "afname", export: "injectie", idle: "rust",
  "Self-sufficiency": "Zelfvoorziening", "Self-consumption": "Eigen verbruik",
  "Net cost today": "Netto kost vandaag", "Heat pump today": "Warmtepomp vandaag",
  "Car today": "Auto vandaag", "Peak this month": "Piek deze maand",
  "Solar today": "Zon vandaag", "House today": "Huis vandaag", Energy: "Energie",
  charging: "laden", discharging: "ontladen",
  "Home Energy Monitor not found. Set it up under Settings → Devices & services.":
    "Home Energy Monitor niet gevonden. Stel het in via Instellingen → Apparaten & diensten.",
};

const fmtPower = (w) => {
  const a = Math.abs(w || 0);
  if (a < 1000) return `${Math.round(a)} W`;
  return `${(a / 1000).toFixed(a < 10000 ? 2 : 1)} kW`;
};

const batteryIcon = (soc, charging) => {
  if (soc == null || isNaN(soc)) return charging ? "mdi:battery-charging" : "mdi:battery-high";
  const step = Math.max(10, Math.min(100, Math.round(soc / 10) * 10));
  if (charging) return step === 100 ? "mdi:battery-charging-100" : `mdi:battery-charging-${step}`;
  return step === 100 ? "mdi:battery" : `mdi:battery-${step}`;
};

class HomeEnergyCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigElement() {
    return undefined;
  }

  setConfig(config) {
    this._config = { show_stats: true, ...(config || {}) };
    this._sig = undefined;
    if (this.shadowRoot) this.shadowRoot.innerHTML = "";
    this._built = false;
  }

  getCardSize() {
    return 7;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _t(s) {
    const lang = (this._hass && (this._hass.locale?.language || this._hass.language)) || "en";
    return lang.startsWith("nl") ? NL[s] || s : s;
  }

  _mainEntity() {
    if (this._config.entity) return this._config.entity;
    if (this._discovered) return this._discovered;
    const ents = (this._hass && this._hass.entities) || {};
    const hit = Object.values(ents).find(
      (e) => e.platform === "home_energy_monitor" && e.translation_key === "house_power"
    );
    if (hit) this._discovered = hit.entity_id;
    else if (this._hass.states["sensor.home_energy_house_power"]) this._discovered = "sensor.home_energy_house_power";
    return this._discovered;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config) return;
    const id = this._mainEntity();
    const main = id ? hass.states[id] : undefined;
    const map = (main && main.attributes.entities) || {};
    const watched = [id, ...Object.values(map)];
    const sig =
      watched.map((e) => (e && hass.states[e] ? hass.states[e].last_updated : "-")).join("|") +
      (hass.themes && hass.themes.darkMode) + (hass.locale && hass.locale.language);
    if (sig === this._sig) return;
    this._sig = sig;
    if (!main) {
      this._renderMissing();
      return;
    }
    const conf = main.attributes.configured || {};
    const confSig = JSON.stringify(conf) + this._t("Home");
    if (!this._built || this._confSig !== confSig) {
      this._build(conf);
      this._confSig = confSig;
    }
    this._update(main, map);
  }

  _ensureRoot() {
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    return this.shadowRoot;
  }

  _renderMissing() {
    this._built = false;
    this._ensureRoot().innerHTML = `
      <ha-card><div style="padding:16px">${this._t(
        "Home Energy Monitor not found. Set it up under Settings → Devices & services."
      )}</div></ha-card>`;
  }

  _build(conf) {
    const ok = (req) => req.every((r) => conf[r]);
    const lines = Object.entries(LINES)
      .filter(([, l]) => ok(l[3]))
      .map(([id, [from, to, color]]) => {
        const [x1, y1] = POS[from];
        const [x2, y2] = POS[to];
        const d = `M${x1} ${y1} L${x2} ${y2}`;
        return `<path class="track" d="${d}"/><path class="flow idle" data-line="${id}" d="${d}" style="stroke:${color}"/>`;
      })
      .join("");

    const nodes = Object.entries(NODES)
      .filter(([, n]) => ok(n.requires))
      .map(([k, n]) => {
        const [x, y] = POS[k];
        return `
          <div class="node ${n.big ? "big" : ""}" data-node="${k}"
               style="left:${(x / 500) * 100}%;top:${(y / 360) * 100}%;--c:${n.color}">
            <div class="circle">
              <ha-icon icon="${n.icon}"></ha-icon>
              <span class="val">–</span>
              <span class="sub"></span>
            </div>
            <div class="lbl">${this._t(n.label)}</div>
          </div>`;
      })
      .join("");

    const title = this._config.title;
    this._ensureRoot().innerHTML = `
      <style>
        :host { display:block; }
        ha-card { padding: 8px 16px 16px; overflow: hidden; }
        .title { font-size: 1.1rem; font-weight: 500; padding: 8px 0 0; color: var(--primary-text-color); }
        .flowbox { position: relative; width: 100%; max-width: 520px; margin: 0 auto; aspect-ratio: 500 / 360; }
        svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
        .track { fill: none; stroke: var(--divider-color, rgba(127,127,127,.25)); stroke-width: 1.5; }
        .flow { fill: none; stroke-width: 3; stroke-linecap: round; stroke-dasharray: 0.1 11;
                animation: dash var(--dur, 2s) linear infinite; }
        .flow.rev { animation-direction: reverse; }
        .flow.idle { opacity: 0; animation: none; }
        @keyframes dash { to { stroke-dashoffset: -11.1; } }
        @media (prefers-reduced-motion: reduce) {
          .flow { animation: none; stroke-dasharray: none; opacity: .7; }
          .flow.idle { opacity: 0; }
        }
        .node { position: absolute; transform: translate(-50%, -50%); display: flex; flex-direction: column;
                align-items: center; cursor: pointer; -webkit-tap-highlight-color: transparent; }
        .circle { width: 64px; height: 64px; border-radius: 50%; border: 2px solid var(--c);
                  background: var(--card-background-color, var(--ha-card-background, #fff));
                  display: flex; flex-direction: column; align-items: center; justify-content: center;
                  box-sizing: border-box; line-height: 1.15; }
        .node.big .circle { width: 78px; height: 78px; border-width: 3px; }
        .circle ha-icon { --mdc-icon-size: 20px; color: var(--c); }
        .val { font-size: 12px; font-weight: 600; color: var(--primary-text-color); white-space: nowrap; }
        .sub { font-size: 10px; color: var(--secondary-text-color); white-space: nowrap; }
        .sub:empty { display: none; }
        .lbl { margin-top: 2px; font-size: 11px; color: var(--secondary-text-color);
               background: var(--card-background-color, var(--ha-card-background, #fff)); padding: 0 4px; border-radius: 4px; }
        .node.dim .circle { opacity: .55; }
        @media (max-width: 420px) {
          .circle { width: 54px; height: 54px; }
          .node.big .circle { width: 66px; height: 66px; }
          .circle ha-icon { --mdc-icon-size: 17px; }
          .val { font-size: 11px; }
        }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-top: 12px; }
        .stat { border-radius: 10px; padding: 8px 10px; cursor: pointer;
                background: var(--secondary-background-color, rgba(127,127,127,.08)); }
        .stat .k { font-size: 11px; color: var(--secondary-text-color); }
        .stat .v { font-size: 15px; font-weight: 600; color: var(--primary-text-color); margin-top: 2px; }
        .stat .s { font-size: 11px; color: var(--secondary-text-color); }
        .stat .s:empty { display: none; }
      </style>
      <ha-card>
        ${title ? `<div class="title">${title}</div>` : ""}
        <div class="flowbox">
          <svg viewBox="0 0 500 360" preserveAspectRatio="xMidYMid meet">${lines}</svg>
          ${nodes}
        </div>
        <div class="stats"></div>
      </ha-card>`;

    this.shadowRoot.querySelectorAll(".node").forEach((el) =>
      el.addEventListener("click", () => this._moreInfo(this._nodeEntity(el.dataset.node)))
    );
    this.shadowRoot.querySelector(".stats").addEventListener("click", (ev) => {
      const tile = ev.target.closest(".stat");
      if (tile) this._moreInfo(tile.dataset.entity);
    });
    this._built = true;
  }

  _nodeEntity(node) {
    const map = this._map || {};
    return {
      solar: map.solar_today,
      grid: map.grid_import_today,
      battery: map.battery_discharge_energy,
      home: this._mainEntity(),
      heat_pump: map.heat_pump_today,
      ev: map.ev_today,
      other: map.other_power,
    }[node];
  }

  _moreInfo(entityId) {
    if (!entityId) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  _setLine(id, watts, reverse = false) {
    const el = this.shadowRoot.querySelector(`[data-line="${id}"]`);
    if (!el) return;
    const w = Math.abs(watts || 0);
    if (w < 10) {
      el.classList.add("idle");
      return;
    }
    el.classList.remove("idle");
    el.classList.toggle("rev", reverse);
    const dur = Math.max(0.35, 3 - Math.log10(w) * 0.7);
    el.style.setProperty("--dur", `${dur.toFixed(2)}s`);
  }

  _setNode(node, val, sub = "", icon = null, dim = false) {
    const el = this.shadowRoot.querySelector(`[data-node="${node}"]`);
    if (!el) return;
    el.querySelector(".val").textContent = val;
    el.querySelector(".sub").textContent = sub;
    if (icon) el.querySelector("ha-icon").setAttribute("icon", icon);
    el.classList.toggle("dim", dim);
  }

  _fmt(entityId) {
    const st = entityId && this._hass.states[entityId];
    if (!st || st.state === "unknown" || st.state === "unavailable") return "–";
    if (this._hass.formatEntityState) return this._hass.formatEntityState(st);
    const u = st.attributes.unit_of_measurement;
    return u ? `${st.state} ${u}` : st.state;
  }

  _update(main, map) {
    this._map = map;
    const a = main.attributes;
    const f = a.flows || {};
    const conf = a.configured || {};
    const cur = a.currency === "EUR" || !a.currency ? "€" : a.currency;

    // lines
    this._setLine("solar_to_home", f.solar_to_home);
    this._setLine("solar_to_grid", f.solar_to_grid);
    this._setLine("solar_to_battery", f.solar_to_battery);
    this._setLine("grid_to_home", f.grid_to_home);
    const gb = (f.grid_to_battery || 0) - (f.battery_to_grid || 0);
    this._setLine("grid_battery", gb, gb < 0);
    this._setLine("battery_to_home", f.battery_to_home);
    this._setLine("home_to_heat_pump", f.heat_pump);
    this._setLine("home_to_ev", f.ev);
    this._setLine("home_to_other", f.other);

    // nodes
    this._setNode("solar", fmtPower(f.solar), "", null, (f.solar || 0) < 10);
    const grid = a.grid_power || 0;
    const price = a.price_import != null ? `${cur}${Number(a.price_import).toFixed(3)}/kWh` : "";
    const dir = grid > 10 ? this._t("import") : grid < -10 ? this._t("export") : this._t("idle");
    this._setNode("grid", fmtPower(grid), price || dir);
    if (conf.battery) {
      const soc = a.battery_soc;
      const charging = (a.battery_power || 0) < -10;
      this._setNode(
        "battery",
        fmtPower(a.battery_power),
        soc != null ? `${Math.round(soc)}%` : charging ? this._t("charging") : "",
        batteryIcon(soc, charging)
      );
    }
    this._setNode("home", fmtPower(f.house));
    this._setNode("heat_pump", fmtPower(f.heat_pump), "", null, (f.heat_pump || 0) < 10);
    this._setNode("ev", fmtPower(f.ev), "", null, (f.ev || 0) < 10);
    this._setNode("other", fmtPower(f.other));

    // stat tiles
    if (!this._config.show_stats) {
      this.shadowRoot.querySelector(".stats").innerHTML = "";
      return;
    }
    const tiles = [
      ["Self-sufficiency", map.self_sufficiency_today, ""],
      ["Self-consumption", map.self_consumption_today, ""],
      ["Net cost today", map.net_cost_today, map.grid_import_today ? `${this._fmt(map.grid_import_today)} ${this._t("import")}` : ""],
      ["Heat pump today", map.heat_pump_today, map.heat_pump_cost_today ? this._fmt(map.heat_pump_cost_today) : ""],
      ["Car today", map.ev_today, map.ev_cost_today ? this._fmt(map.ev_cost_today) : ""],
      ["Peak this month", map.month_peak, map.quarter_peak ? `${this._t("now")} ${this._fmt(map.quarter_peak)}` : ""],
    ].filter(([, e]) => e && this._hass.states[e]);
    this.shadowRoot.querySelector(".stats").innerHTML = tiles
      .map(
        ([k, e, s]) =>
          `<div class="stat" data-entity="${e}"><div class="k">${this._t(k)}</div><div class="v">${this._fmt(e)}</div><div class="s">${s}</div></div>`
      )
      .join("");
  }
}

NL.now = "nu";

if (!customElements.get("home-energy-card")) {
  customElements.define("home-energy-card", HomeEnergyCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "home-energy-card",
    name: "Home Energy Card",
    description: "Live energy flows between grid, solar, battery, heat pump and car, with today's costs.",
    preview: true,
  });
  console.info(`%c HOME-ENERGY-CARD %c v${CARD_VERSION} `, "background:#ff9800;color:#fff", "");
}
