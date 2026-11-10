"""Engine: reads the source sensors, integrates energy and cost, persists totals."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .calc import Flows, PowerSnapshot, compute_flows, to_eur_per_kwh, to_watts
from .const import (
    CONF_BATTERY,
    CONF_BATTERY_INVERT,
    CONF_BATTERY_SOC,
    CONF_EV,
    CONF_GRID,
    CONF_GRID_EXPORT,
    CONF_GRID_INVERT,
    CONF_HEAT_PUMP,
    CONF_PRICE_EXPORT,
    CONF_PRICE_IMPORT,
    CONF_SOLAR,
    DOMAIN,
    FAST_INTERVAL_S,
    MAX_GAP_S,
    SLOW_INTERVAL_S,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Energy counters (kWh) integrated from the flows
ENERGY_KEYS = (
    "house",
    "heat_pump",
    "ev",
    "other",
    "solar",
    "grid_import",
    "grid_export",
    "battery_charge",
    "battery_discharge",
    "solar_to_home",
    "solar_to_battery",
    "solar_to_grid",
    "grid_to_home",
    "grid_to_battery",
    "battery_to_home",
    "battery_to_grid",
)
# Money counters (currency) integrated from flows x price
COST_KEYS = ("import_cost", "export_revenue", "heat_pump_cost", "ev_cost", "other_cost")


class EnergyEngine:
    """Keeps live flows and accumulated energy/cost for one config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str, conf: dict[str, Any]) -> None:
        self.hass = hass
        self.conf = conf
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}"
        )

        self.totals: dict[str, float] = {}
        self.today: dict[str, float] = {}
        self.today_date: str | None = None
        self.month: str | None = None
        self.month_peak_kw: float = 0.0
        self.month_peak_start: str | None = None
        self.quarter_start: str | None = None
        self.quarter_kwh: float = 0.0

        self.snapshot = PowerSnapshot()
        self.flows: Flows = compute_flows(self.snapshot)
        self.price_import: float | None = None
        self.price_export: float | None = None
        self.battery_soc: float | None = None

        # entity_ids of our own sensors, keyed by sensor key (handed to the card)
        self.entity_ids: dict[str, str] = {}

        self._last_update: datetime | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._fast_listeners: list[Callable[[], None]] = []
        self._slow_listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------------ config
    def has(self, key: str) -> bool:
        return bool(self.conf.get(key))

    @property
    def has_battery(self) -> bool:
        return self.has(CONF_BATTERY)

    @property
    def has_solar(self) -> bool:
        return self.has(CONF_SOLAR)

    @property
    def has_prices(self) -> bool:
        return self.has(CONF_PRICE_IMPORT)

    # ------------------------------------------------------------- persistence
    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.totals = {k: float(v) for k, v in data.get("totals", {}).items()}
        self.today = {k: float(v) for k, v in data.get("today", {}).items()}
        self.today_date = data.get("today_date")
        self.month = data.get("month")
        self.month_peak_kw = float(data.get("month_peak_kw", 0.0))
        self.month_peak_start = data.get("month_peak_start")
        self.quarter_start = data.get("quarter_start")
        self.quarter_kwh = float(data.get("quarter_kwh", 0.0))

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "totals": self.totals,
            "today": self.today,
            "today_date": self.today_date,
            "month": self.month,
            "month_peak_kw": self.month_peak_kw,
            "month_peak_start": self.month_peak_start,
            "quarter_start": self.quarter_start,
            "quarter_kwh": self.quarter_kwh,
        }

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._process(dt_util.utcnow())
        await self._store.async_save(self._data_to_save())

    # --------------------------------------------------------------- listeners
    @callback
    def async_add_listener(self, fast: bool, cb: Callable[[], None]) -> Callable[[], None]:
        target = self._fast_listeners if fast else self._slow_listeners
        target.append(cb)

        @callback
        def _remove() -> None:
            if cb in target:
                target.remove(cb)

        return _remove

    @callback
    def async_start(self) -> None:
        sources = [
            self.conf[k]
            for k in (
                CONF_GRID,
                CONF_GRID_EXPORT,
                CONF_SOLAR,
                CONF_BATTERY,
                CONF_BATTERY_SOC,
                CONF_HEAT_PUMP,
                CONF_EV,
                CONF_PRICE_IMPORT,
                CONF_PRICE_EXPORT,
            )
            if self.conf.get(k)
        ]
        self._unsubs.append(
            async_track_state_change_event(self.hass, sources, self._on_source_change)
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._on_fast_tick, timedelta(seconds=FAST_INTERVAL_S)
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._on_slow_tick, timedelta(seconds=SLOW_INTERVAL_S)
            )
        )
        self._process(dt_util.utcnow())
        self._notify(self._fast_listeners)
        self._notify(self._slow_listeners)

    @callback
    def _on_source_change(self, _event: Event) -> None:
        self._process(dt_util.utcnow())

    @callback
    def _on_fast_tick(self, now: datetime) -> None:
        self._process(now)
        self._notify(self._fast_listeners)

    @callback
    def _on_slow_tick(self, now: datetime) -> None:
        self._process(now)
        self._notify(self._slow_listeners)
        self._store.async_delay_save(self._data_to_save, 30)

    @staticmethod
    def _notify(listeners: list[Callable[[], None]]) -> None:
        for cb in list(listeners):
            cb()

    # ------------------------------------------------------------------- core
    @callback
    def _process(self, now: datetime) -> None:
        """Integrate since the last update, handle period rollovers, re-read sources."""
        local = dt_util.as_local(now)
        if self._last_update is not None:
            dt = (now - self._last_update).total_seconds()
            if 0 < dt <= MAX_GAP_S:
                self._accumulate(dt / 3600.0)
        self._rollover(local)
        self._read_sources()
        self.flows = compute_flows(self.snapshot)
        self._last_update = now

    def _add(self, key: str, value: float) -> None:
        self.totals[key] = self.totals.get(key, 0.0) + value
        self.today[key] = self.today.get(key, 0.0) + value

    def _accumulate(self, hours: float) -> None:
        """Add energy/cost for the elapsed period using the flows that held during it."""
        f = self.flows
        for key in ENERGY_KEYS:
            self._add(key, getattr(f, key) / 1000.0 * hours)

        if self.price_import is not None:
            price = self.price_import
            self._add("import_cost", f.grid_import / 1000.0 * hours * price)
            # Each consumer pays for the share of its power that came from the grid.
            share = f.grid_share
            self._add("heat_pump_cost", f.heat_pump / 1000.0 * hours * share * price)
            self._add("ev_cost", f.ev / 1000.0 * hours * share * price)
            self._add("other_cost", f.other / 1000.0 * hours * share * price)
        if self.price_export is not None:
            self._add("export_revenue", f.grid_export / 1000.0 * hours * self.price_export)

        # Capacity tariff: average import power per quarter hour.
        self.quarter_kwh += f.grid_import / 1000.0 * hours
        quarter_kw = self.quarter_kwh * 4
        if quarter_kw > self.month_peak_kw:
            self.month_peak_kw = quarter_kw
            self.month_peak_start = self.quarter_start

    def _rollover(self, local: datetime) -> None:
        date = local.date().isoformat()
        if self.today_date != date:
            self.today = {}
            self.today_date = date

        month = local.strftime("%Y-%m")
        if self.month != month:
            self.month = month
            self.month_peak_kw = 0.0
            self.month_peak_start = None

        q = local.replace(minute=local.minute // 15 * 15, second=0, microsecond=0)
        q_iso = q.isoformat()
        if self.quarter_start != q_iso:
            self.quarter_start = q_iso
            self.quarter_kwh = 0.0

    def _read_sources(self) -> None:
        grid = self._power(CONF_GRID)
        if self.has(CONF_GRID_EXPORT):
            grid -= self._power(CONF_GRID_EXPORT)
        if self.conf.get(CONF_GRID_INVERT):
            grid = -grid

        battery = self._power(CONF_BATTERY)
        if self.conf.get(CONF_BATTERY_INVERT):
            battery = -battery

        self.snapshot = PowerSnapshot(
            grid=grid,
            solar=self._power(CONF_SOLAR),
            battery=battery,
            heat_pump=self._power(CONF_HEAT_PUMP),
            ev=self._power(CONF_EV),
        )
        self.price_import = self._price(CONF_PRICE_IMPORT)
        self.price_export = self._price(CONF_PRICE_EXPORT)
        self.battery_soc = self._number(CONF_BATTERY_SOC)

    def _number(self, key: str) -> float | None:
        entity_id = self.conf.get(key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE, ""):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _unit(self, key: str) -> str | None:
        state = self.hass.states.get(self.conf.get(key, ""))
        return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None

    def _power(self, key: str) -> float:
        value = self._number(key)
        if value is None:
            return 0.0
        return to_watts(value, self._unit(key))

    def _price(self, key: str) -> float | None:
        value = self._number(key)
        if value is None:
            return None
        return to_eur_per_kwh(value, self._unit(key))

    # ------------------------------------------------------------ derived values
    def today_value(self, key: str) -> float:
        return self.today.get(key, 0.0)

    def total_value(self, key: str) -> float:
        return self.totals.get(key, 0.0)

    def self_sufficiency_today(self) -> float | None:
        house = self.today_value("house")
        if house <= 0.001:
            return None
        return max(0.0, min(100.0, (house - self.today_value("grid_to_home")) / house * 100))

    def self_consumption_today(self) -> float | None:
        solar = self.today_value("solar")
        if solar <= 0.001:
            return None
        return max(0.0, min(100.0, (solar - self.today_value("solar_to_grid")) / solar * 100))

    def net_cost_today(self) -> float:
        return self.today_value("import_cost") - self.today_value("export_revenue")

    def quarter_kw(self) -> float:
        return self.quarter_kwh * 4
