"""Sensors for Home Energy Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    MATCH_ALL,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeEnergyConfigEntry
from .const import (
    CONF_EV,
    CONF_HEAT_PUMP,
    CONF_PRICE_EXPORT,
    CONF_PRICE_IMPORT,
    DOMAIN,
    VERSION,
)
from .engine import EnergyEngine

# requirement tags -> test on the engine
_REQ: dict[str, Callable[[EnergyEngine], bool]] = {
    "solar": lambda e: e.has_solar,
    "battery": lambda e: e.has_battery,
    "heat_pump": lambda e: e.has(CONF_HEAT_PUMP),
    "ev": lambda e: e.has(CONF_EV),
    "price": lambda e: e.has(CONF_PRICE_IMPORT),
    "export_price": lambda e: e.has(CONF_PRICE_EXPORT),
}


@dataclass(frozen=True, kw_only=True)
class HomeEnergySensorDescription(SensorEntityDescription):
    value_fn: Callable[[EnergyEngine], Any]
    fast: bool = False
    requires: tuple[str, ...] = field(default_factory=tuple)


def _energy_total(key: str, *requires: str) -> HomeEnergySensorDescription:
    return HomeEnergySensorDescription(
        key=f"{key}_energy",
        translation_key=f"{key}_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda e, k=key: round(e.total_value(k), 4),
        requires=requires,
    )


def _energy_today(key: str, *requires: str) -> HomeEnergySensorDescription:
    return HomeEnergySensorDescription(
        key=f"{key}_today",
        translation_key=f"{key}_today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=lambda e, k=key: round(e.today_value(k), 4),
        requires=requires,
    )


def _money_total(key: str, *requires: str) -> HomeEnergySensorDescription:
    return HomeEnergySensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=2,
        value_fn=lambda e, k=key: round(e.total_value(k), 4),
        requires=requires,
    )


def _money_today(key: str, *requires: str) -> HomeEnergySensorDescription:
    # No state_class: these reset daily; long-term statistics come from the totals.
    return HomeEnergySensorDescription(
        key=f"{key}_today",
        translation_key=f"{key}_today",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value_fn=lambda e, k=key: round(e.today_value(k), 4),
        requires=requires,
    )


SENSORS: tuple[HomeEnergySensorDescription, ...] = (
    # --- live power (updated every 10 s) ---
    HomeEnergySensorDescription(
        key="house_power",
        translation_key="house_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda e: round(e.flows.house, 1),
        fast=True,
    ),
    HomeEnergySensorDescription(
        key="other_power",
        translation_key="other_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda e: round(e.flows.other, 1),
        fast=True,
    ),
    # --- capacity tariff (Flanders: monthly peak of 15-min average import) ---
    HomeEnergySensorDescription(
        key="quarter_peak",
        translation_key="quarter_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=lambda e: round(e.quarter_kw(), 3),
        fast=True,
    ),
    HomeEnergySensorDescription(
        key="month_peak",
        translation_key="month_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=lambda e: round(e.month_peak_kw, 3),
        fast=True,
    ),
    # --- lifetime energy (for statistics & the built-in Energy dashboard) ---
    _energy_total("house"),
    _energy_total("other"),
    _energy_total("heat_pump", "heat_pump"),
    _energy_total("ev", "ev"),
    _energy_total("solar", "solar"),
    _energy_total("grid_import"),
    _energy_total("grid_export"),
    _energy_total("battery_charge", "battery"),
    _energy_total("battery_discharge", "battery"),
    _energy_total("solar_to_home", "solar"),
    _energy_total("battery_to_home", "battery"),
    _energy_total("grid_to_home"),
    # --- today ---
    _energy_today("house"),
    _energy_today("heat_pump", "heat_pump"),
    _energy_today("ev", "ev"),
    _energy_today("solar", "solar"),
    _energy_today("grid_import"),
    _energy_today("grid_export"),
    HomeEnergySensorDescription(
        key="self_sufficiency_today",
        translation_key="self_sufficiency_today",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda e: (
            None if (v := e.self_sufficiency_today()) is None else round(v, 1)
        ),
    ),
    HomeEnergySensorDescription(
        key="self_consumption_today",
        translation_key="self_consumption_today",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda e: (
            None if (v := e.self_consumption_today()) is None else round(v, 1)
        ),
        requires=("solar",),
    ),
    # --- costs (dynamic prices) ---
    _money_total("import_cost", "price"),
    _money_total("export_revenue", "export_price"),
    _money_total("heat_pump_cost", "price", "heat_pump"),
    _money_total("ev_cost", "price", "ev"),
    HomeEnergySensorDescription(
        key="net_cost_today",
        translation_key="net_cost_today",
        device_class=SensorDeviceClass.MONETARY,
        suggested_display_precision=2,
        value_fn=lambda e: round(e.net_cost_today(), 4),
        requires=("price",),
    ),
    _money_today("heat_pump_cost", "price", "heat_pump"),
    _money_today("ev_cost", "price", "ev"),
    _money_today("other_cost", "price"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeEnergyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    engine = entry.runtime_data
    device = DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Home Energy Monitor",
        model="Energy flow calculator",
        sw_version=VERSION,
        entry_type=DeviceEntryType.SERVICE,
    )
    entities: list[HomeEnergySensor] = []
    for desc in SENSORS:
        if all(_REQ[r](engine) for r in desc.requires):
            cls = HousePowerSensor if desc.key == "house_power" else HomeEnergySensor
            entities.append(cls(engine, entry.entry_id, device, desc))
    async_add_entities(entities)


class HomeEnergySensor(SensorEntity):
    """A value computed by the engine."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_description: HomeEnergySensorDescription

    def __init__(
        self,
        engine: EnergyEngine,
        entry_id: str,
        device: DeviceInfo,
        description: HomeEnergySensorDescription,
    ) -> None:
        self.entity_description = description
        self._engine = engine
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = device
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = engine.hass.config.currency

    async def async_added_to_hass(self) -> None:
        self._engine.entity_ids[self.entity_description.key] = self.entity_id
        self.async_on_remove(
            self._engine.async_add_listener(self.entity_description.fast, self._update)
        )

    async def async_will_remove_from_hass(self) -> None:
        self._engine.entity_ids.pop(self.entity_description.key, None)

    @callback
    def _update(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._engine)


class HousePowerSensor(HomeEnergySensor):
    """House power, carrying all live flows as attributes for the dashboard card."""

    # Live detail changes every update; keep it out of the database.
    _unrecorded_attributes = frozenset({MATCH_ALL})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        e = self._engine
        return {
            "flows": e.flows.as_dict(),
            "grid_power": round(e.snapshot.grid, 1),
            "battery_power": round(e.snapshot.battery, 1),
            "battery_soc": e.battery_soc,
            "price_import": e.price_import,
            "price_export": e.price_export,
            "currency": e.hass.config.currency,
            "configured": {
                "solar": e.has_solar,
                "battery": e.has_battery,
                "heat_pump": e.has(CONF_HEAT_PUMP),
                "ev": e.has(CONF_EV),
                "prices": e.has_prices,
            },
            "entities": dict(e.entity_ids),
        }
