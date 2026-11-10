"""Pure power-flow maths (no Home Assistant imports, so it is easy to test).

Sign conventions used throughout:
  grid    > 0  importing from the grid,   < 0 exporting
  battery > 0  battery discharging,       < 0 charging
  solar, heat_pump, ev are always >= 0
All values in watts.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class PowerSnapshot:
    grid: float = 0.0
    solar: float = 0.0
    battery: float = 0.0
    heat_pump: float = 0.0
    ev: float = 0.0


@dataclass
class Flows:
    house: float = 0.0
    heat_pump: float = 0.0
    ev: float = 0.0
    other: float = 0.0
    solar: float = 0.0
    grid_import: float = 0.0
    grid_export: float = 0.0
    battery_charge: float = 0.0
    battery_discharge: float = 0.0
    solar_to_home: float = 0.0
    solar_to_battery: float = 0.0
    solar_to_grid: float = 0.0
    grid_to_home: float = 0.0
    grid_to_battery: float = 0.0
    battery_to_home: float = 0.0
    battery_to_grid: float = 0.0

    @property
    def grid_share(self) -> float:
        """Fraction of the current house consumption supplied by the grid."""
        if self.house <= 0:
            return 0.0
        return min(self.grid_to_home / self.house, 1.0)

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 1) for k, v in asdict(self).items()}


def compute_flows(s: PowerSnapshot) -> Flows:
    """Split the measured powers into flows between grid, solar, battery and home.

    Priority used when allocating: solar feeds the house first, then the
    battery, and only the remainder is exported. The battery feeds the house
    before it feeds the grid. Whatever the house still needs comes from the grid.
    """
    solar = max(s.solar, 0.0)
    grid_import = max(s.grid, 0.0)
    grid_export = max(-s.grid, 0.0)
    bat_dis = max(s.battery, 0.0)
    bat_chg = max(-s.battery, 0.0)

    # Energy balance: everything going in minus everything going out.
    house = max(solar + s.grid + s.battery, 0.0)

    solar_to_home = min(solar, house)
    solar_left = solar - solar_to_home

    solar_to_battery = min(solar_left, bat_chg)
    solar_left -= solar_to_battery
    grid_to_battery = max(bat_chg - solar_to_battery, 0.0)

    battery_to_home = min(bat_dis, max(house - solar_to_home, 0.0))
    battery_to_grid = max(bat_dis - battery_to_home, 0.0)

    solar_to_grid = max(solar_left, 0.0)
    grid_to_home = max(house - solar_to_home - battery_to_home, 0.0)

    # Sub-meters can never exceed the total (sensor timing noise).
    heat_pump = min(max(s.heat_pump, 0.0), house)
    ev = min(max(s.ev, 0.0), max(house - heat_pump, 0.0))
    other = max(house - heat_pump - ev, 0.0)

    return Flows(
        house=house,
        heat_pump=heat_pump,
        ev=ev,
        other=other,
        solar=solar,
        grid_import=grid_import,
        grid_export=grid_export,
        battery_charge=bat_chg,
        battery_discharge=bat_dis,
        solar_to_home=solar_to_home,
        solar_to_battery=solar_to_battery,
        solar_to_grid=solar_to_grid,
        grid_to_home=grid_to_home,
        grid_to_battery=grid_to_battery,
        battery_to_home=battery_to_home,
        battery_to_grid=battery_to_grid,
    )


def to_watts(value: float, unit: str | None) -> float:
    """Normalise a power reading to W."""
    factor = {"kW": 1000.0, "MW": 1_000_000.0, "mW": 0.001}.get((unit or "W").strip(), 1.0)
    return value * factor


def to_eur_per_kwh(value: float, unit: str | None) -> float:
    """Normalise a price to <currency>/kWh. Handles /MWh, /Wh and cent prices."""
    u = (unit or "").replace(" ", "")
    if "MWh" in u:
        value /= 1000.0
    elif "/Wh" in u:
        value *= 1000.0
    lower = u.lower()
    if lower.startswith(("ct", "c€", "cent", "c/")):
        value /= 100.0
    return value
