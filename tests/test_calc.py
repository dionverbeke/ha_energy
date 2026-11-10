"""Tests for the pure power-flow maths."""

import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "calc", Path(__file__).parents[1] / "custom_components/home_energy_monitor/calc.py"
)
calc = importlib.util.module_from_spec(_spec)
sys.modules["calc"] = calc
_spec.loader.exec_module(calc)
S, compute = calc.PowerSnapshot, calc.compute_flows


def balanced(f, s):
    """Grid & battery measured must equal the sum of their flows."""
    assert f.grid_to_home + f.grid_to_battery - f.solar_to_grid - f.battery_to_grid == pytest.approx(s.grid)
    assert f.battery_to_home + f.battery_to_grid - f.solar_to_battery - f.grid_to_battery == pytest.approx(s.battery)
    assert f.solar_to_home + f.solar_to_battery + f.solar_to_grid == pytest.approx(s.solar)
    assert f.solar_to_home + f.battery_to_home + f.grid_to_home == pytest.approx(f.house)
    assert f.heat_pump + f.ev + f.other == pytest.approx(f.house)


def test_night_grid_only():
    s = S(grid=2500, heat_pump=1800)
    f = compute(s)
    assert f.house == 2500 and f.grid_to_home == 2500 and f.other == 700
    assert f.grid_share == 1.0
    balanced(f, s)


def test_sunny_export_and_charge():
    # 6 kW solar, house 1.5 kW, battery charging 2 kW, export 2.5 kW
    s = S(grid=-2500, solar=6000, battery=-2000)
    f = compute(s)
    assert f.house == 1500
    assert f.solar_to_home == 1500 and f.solar_to_battery == 2000 and f.solar_to_grid == 2500
    assert f.grid_share == 0
    balanced(f, s)


def test_battery_covers_evening_with_ev_from_grid():
    # battery 3 kW discharge, car 7.4 kW, grid makes up the rest
    s = S(grid=5000, battery=3000, ev=7400, heat_pump=400)
    f = compute(s)
    assert f.house == 8000
    assert f.battery_to_home == 3000 and f.grid_to_home == 5000
    assert f.ev == 7400 and f.heat_pump == 400 and f.other == 200
    assert f.grid_share == pytest.approx(0.625)
    balanced(f, s)


def test_grid_charges_battery_at_cheap_hour():
    s = S(grid=4000, battery=-3500)
    f = compute(s)
    assert f.house == 500 and f.grid_to_battery == 3500 and f.grid_to_home == 500
    balanced(f, s)


def test_battery_exports():
    s = S(grid=-2000, battery=2600)
    f = compute(s)
    assert f.house == 600 and f.battery_to_home == 600 and f.battery_to_grid == 2000
    balanced(f, s)


def test_submeters_clamped_to_house():
    f = compute(S(grid=1000, heat_pump=1200, ev=500))
    assert f.heat_pump == 1000 and f.ev == 0 and f.other == 0


def test_units():
    assert calc.to_watts(2.5, "kW") == 2500
    assert calc.to_watts(300, "W") == 300
    assert calc.to_eur_per_kwh(120, "€/MWh") == pytest.approx(0.12)
    assert calc.to_eur_per_kwh(25, "c€/kWh") == pytest.approx(0.25)
    assert calc.to_eur_per_kwh(0.31, "EUR/kWh") == pytest.approx(0.31)
    assert calc.to_eur_per_kwh(-0.02, "€/kWh") == pytest.approx(-0.02)
