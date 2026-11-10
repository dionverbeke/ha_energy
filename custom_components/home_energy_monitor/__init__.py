"""Home Energy Monitor: energy flows, per-device use and dynamic-price costs."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CARD_URL, DOMAIN, VERSION
from .engine import EnergyEngine

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type HomeEnergyConfigEntry = ConfigEntry[EnergyEngine]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled dashboard card so no separate install is needed."""
    from homeassistant.components.frontend import add_extra_js_url
    from homeassistant.components.http import StaticPathConfig

    card = Path(__file__).parent / "frontend" / "home-energy-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(card), False)]
    )
    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")
    return True


def _conf(entry: ConfigEntry) -> dict:
    # The options flow stores the full set of fields, so options win when present.
    return dict(entry.options) if entry.options else dict(entry.data)


async def async_setup_entry(hass: HomeAssistant, entry: HomeEnergyConfigEntry) -> bool:
    engine = EnergyEngine(hass, entry.entry_id, _conf(entry))
    await engine.async_load()
    entry.runtime_data = engine

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    engine.async_start()

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: HomeEnergyConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomeEnergyConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
