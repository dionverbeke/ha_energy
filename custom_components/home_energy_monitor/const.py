"""Constants for Home Energy Monitor."""

from __future__ import annotations

DOMAIN = "home_energy_monitor"
VERSION = "1.0.0"

CARD_URL = f"/{DOMAIN}/home-energy-card.js"

STORAGE_VERSION = 1

# Config keys
CONF_GRID = "grid_power"
CONF_GRID_EXPORT = "grid_export_power"
CONF_GRID_INVERT = "grid_invert"
CONF_SOLAR = "solar_power"
CONF_BATTERY = "battery_power"
CONF_BATTERY_INVERT = "battery_invert"
CONF_BATTERY_SOC = "battery_soc"
CONF_HEAT_PUMP = "heat_pump_power"
CONF_EV = "ev_power"
CONF_PRICE_IMPORT = "price_import"
CONF_PRICE_EXPORT = "price_export"

# How often entity states are pushed to Home Assistant
FAST_INTERVAL_S = 10  # live power values
SLOW_INTERVAL_S = 60  # energy / cost totals

# Gaps longer than this (e.g. after a restart) are not integrated,
# so a long outage doesn't get filled with a stale power value.
MAX_GAP_S = 300
