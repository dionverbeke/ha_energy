"""Config and options flow: pick the sensors that describe your installation."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
)

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
)

_POWER = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.POWER)
)
_SOC = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class=SensorDeviceClass.BATTERY)
)
_ANY_SENSOR = EntitySelector(EntitySelectorConfig(domain="sensor"))

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GRID): _POWER,
        vol.Optional(CONF_GRID_EXPORT): _POWER,
        vol.Optional(CONF_GRID_INVERT, default=False): BooleanSelector(),
        vol.Optional(CONF_SOLAR): _POWER,
        vol.Optional(CONF_BATTERY): _POWER,
        vol.Optional(CONF_BATTERY_INVERT, default=False): BooleanSelector(),
        vol.Optional(CONF_BATTERY_SOC): _SOC,
        vol.Optional(CONF_HEAT_PUMP): _POWER,
        vol.Optional(CONF_EV): _POWER,
        vol.Optional(CONF_PRICE_IMPORT): _ANY_SENSOR,
        vol.Optional(CONF_PRICE_EXPORT): _ANY_SENSOR,
    }
)

_POWER_KEYS = (CONF_GRID, CONF_GRID_EXPORT, CONF_SOLAR, CONF_BATTERY, CONF_HEAT_PUMP, CONF_EV)


def _validate(data: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    seen: dict[str, str] = {}
    for key in _POWER_KEYS:
        entity_id = data.get(key)
        if not entity_id:
            continue
        if entity_id in seen:
            errors[key] = "duplicate_sensor"
        seen[entity_id] = key
    if data.get(CONF_PRICE_EXPORT) and not data.get(CONF_PRICE_IMPORT):
        errors[CONF_PRICE_EXPORT] = "export_without_import"
    return errors


class HomeEnergyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="Home Energy", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HomeEnergyOptionsFlow()


class HomeEnergyOptionsFlow(OptionsFlow):
    """Change the selected sensors later (Settings → Devices → Home Energy Monitor → Configure)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)
        current = user_input or dict(self.config_entry.options or self.config_entry.data)
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(SCHEMA, current),
            errors=errors,
        )
