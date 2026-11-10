# Home Energy Monitor for Home Assistant

Follow where your electricity goes: grid, solar panels, home battery, heat pump and car charger — live, per day, and in euros with a dynamic tariff. Includes a live energy-flow dashboard card and tracks the Flemish **capacity tariff** (monthly quarter-hour peak).

## What you get

**A dashboard card** (`custom:home-energy-card`) with animated flows between grid, solar, battery, home, heat pump, car and "other", plus tiles for self-sufficiency, self-consumption, today's net cost, heat pump and car usage/cost, and this month's peak. Dutch and English.

**Sensors** (device "Home Energy"):

| Group | Sensors |
|---|---|
| Live | House power (with all flows as attributes), other consumers power |
| Capacity tariff | Current quarter-hour peak, monthly peak (with the quarter it happened in) |
| Lifetime kWh | House, heat pump, car, other, solar, grid import/export, battery in/out, solar used directly, battery used by home, grid used by home |
| Today | House, heat pump, car, solar, import, export kWh; self-sufficiency %; self-consumption % |
| Costs | Import cost, export revenue, heat pump cost, car charging cost (lifetime); net cost, heat pump, car, other (today) |

Heat-pump and car costs only count the part of their power that came **from the grid** at that moment, at the price of that moment. Power from your panels or battery is free in this calculation, so you see what each device really costs you.

## Install

**With HACS (recommended)**
1. In Home Assistant open **HACS**, click **⋮** (top right) → **Custom repositories**.
2. Repository: `https://github.com/dionverbeke/ha_energy`, type: **Integration** → **Add**.
3. Search HACS for **Home Energy Monitor**, open it and click **Download**.
4. Restart Home Assistant (Settings → System → power icon → Restart Home Assistant).

**Manually**
1. Copy `custom_components/home_energy_monitor` into your Home Assistant `config/custom_components/` folder (e.g. with the File editor or Samba add-on).
2. Restart Home Assistant.

## Set up

1. **Settings → Devices & services → Add integration → Home Energy Monitor.**
2. Choose your sensors. Only the grid sensor is required.

| Field | What to pick | Typical source |
|---|---|---|
| Grid power | Net power, positive when importing | P1 / DSMR reader (HomeWizard, Slimmelezer) |
| Grid export power | Only if import and export are separate sensors | P1 reader |
| Solar power | PV production | Inverter integration (SMA, Fronius, SolarEdge, Huawei…) |
| Battery power | Positive = discharging | Battery/hybrid inverter |
| Battery state of charge | % | Battery |
| Heat pump power | Heat pump consumption | Heat pump integration or a smart plug / sub-meter |
| Car charger power | Charger consumption | Charger integration (Wallbox, Easee, Alfen, Zaptec…) |
| Electricity price | Current all-in price per kWh | Dynamic tariff sensor (Nord Pool, ENTSO-e, your supplier) |
| Feed-in price | Current price per exported kWh | Same, or a template sensor |

Units are converted automatically (W/kW, €/kWh, c€/kWh, €/MWh). If a sign is the wrong way round, toggle **Invert grid sign** / **Invert battery sign**. Change sensors any time via **Configure** on the integration.

> **Price sensor tip:** day-ahead sensors usually show the *market* price only. For realistic costs, make a template sensor with your all-in price. Example (adjust to your contract):
> ```yaml
> template:
>   - sensor:
>       - name: "Electricity price all-in"
>         unit_of_measurement: "€/kWh"
>         state: "{{ (states('sensor.nordpool_kwh_be_eur') | float(0) * 1.1 + 0.15) | round(4) }}"
> ```

> **Only showing power sensors without a device class?** The picker lists sensors with device class *power*. If yours is missing, give it `device_class: power` via **Customize** or a template sensor.

## Add the card

The card is bundled with the integration and loaded automatically (refresh the browser once after installing). Edit a dashboard → **Add card** → search **Home Energy Card**, or in YAML:

```yaml
type: custom:home-energy-card
title: Energy            # optional
show_stats: true         # optional, hide the tiles with false
# entity: sensor.home_energy_house_power   # optional, auto-detected
```

## Use with the built-in Energy dashboard

The lifetime kWh sensors work in **Settings → Dashboards → Energy**: add *Heat pump energy*, *Car charger energy* and *Other consumers energy* as **individual devices**. If your inverter or meter doesn't provide kWh counters, you can also use *Solar energy*, *Grid import/export energy* and *Battery charged/discharged energy* there.

## How it calculates

- House consumption = solar + grid + battery (grid positive = import, battery positive = discharge).
- Solar goes to the house first, then the battery, the rest is exported. The battery feeds the house before the grid. The grid supplies whatever is still missing.
- Energy is integrated from power every time a source sensor changes (and at least every 10 s). Gaps longer than 5 minutes (e.g. while Home Assistant is restarting) are skipped rather than guessed.
- Capacity tariff: grid import is averaged per quarter hour (:00, :15, :30, :45); the highest quarter of the month is the monthly peak. Fluvius bills a minimum of 2.5 kW.
- Totals survive restarts. Live sensors update every 10 s and totals every 60 s, to keep the database small.

## Files

```
custom_components/home_energy_monitor/
  __init__.py        setup, serves the card
  config_flow.py     sensor picker (setup + Configure)
  engine.py          reading sensors, integrating energy & cost, persistence
  calc.py            power-flow maths (no HA dependencies)
  sensor.py          the sensors
  frontend/home-energy-card.js
  translations/      en, nl
tests/test_calc.py   unit tests for the flow maths (pytest)
```
