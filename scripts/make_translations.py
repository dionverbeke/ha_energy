"""Generate translations/en.json and translations/nl.json from one table."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "custom_components" / "home_energy_monitor" / "translations"

FIELDS = {
    # key: (en label, en description, nl label, nl description)
    "grid_power": (
        "Grid power",
        "Net grid power (positive = importing). If you have separate import and export sensors, put the import sensor here.",
        "Netvermogen",
        "Netto vermogen van/naar het net (positief = afname). Heb je aparte afname- en injectiesensoren, kies hier de afnamesensor.",
    ),
    "grid_export_power": (
        "Grid export power (optional)",
        "Only if your meter reports export as a separate positive sensor.",
        "Injectievermogen (optioneel)",
        "Alleen als je meter injectie als aparte positieve sensor geeft.",
    ),
    "grid_invert": (
        "Invert grid sign",
        "Turn on if your grid sensor is negative while importing.",
        "Teken net omkeren",
        "Aanzetten als je netsensor negatief is bij afname.",
    ),
    "solar_power": ("Solar power", "Current solar production.", "Zonnepanelen vermogen", "Huidige productie van de zonnepanelen."),
    "battery_power": (
        "Battery power",
        "Positive = discharging, negative = charging (use the invert switch if yours is the other way round).",
        "Batterijvermogen",
        "Positief = ontladen, negatief = laden (gebruik de omkeerschakelaar als het bij jou andersom is).",
    ),
    "battery_invert": (
        "Invert battery sign",
        "Turn on if your battery sensor is positive while charging.",
        "Teken batterij omkeren",
        "Aanzetten als je batterijsensor positief is tijdens het laden.",
    ),
    "battery_soc": ("Battery state of charge", "Battery level in %.", "Laadtoestand batterij", "Batterijniveau in %."),
    "heat_pump_power": ("Heat pump power", "Power used by the heat pump.", "Vermogen warmtepomp", "Verbruik van de warmtepomp."),
    "ev_power": ("Car charger power", "Power used by the EV charger.", "Vermogen laadpaal", "Verbruik van de laadpaal."),
    "price_import": (
        "Electricity price (import)",
        "Sensor with the current all-in price per kWh (€/kWh, c€/kWh or €/MWh are converted automatically).",
        "Elektriciteitsprijs (afname)",
        "Sensor met de huidige all-in prijs per kWh (€/kWh, c€/kWh of €/MWh worden automatisch omgerekend).",
    ),
    "price_export": (
        "Feed-in price (export)",
        "Sensor with the current price you receive per exported kWh.",
        "Injectieprijs",
        "Sensor met de huidige vergoeding per geïnjecteerde kWh.",
    ),
}

ENTITIES = {
    "house_power": ("House power", "Vermogen huis"),
    "other_power": ("Other consumers power", "Vermogen overige verbruikers"),
    "quarter_peak": ("Current quarter-hour peak", "Huidige kwartierpiek"),
    "month_peak": ("Monthly peak (capacity tariff)", "Maandpiek (capaciteitstarief)"),
    "house_energy": ("House energy", "Energie huis"),
    "other_energy": ("Other consumers energy", "Energie overige verbruikers"),
    "heat_pump_energy": ("Heat pump energy", "Energie warmtepomp"),
    "ev_energy": ("Car charger energy", "Energie laadpaal"),
    "solar_energy": ("Solar energy", "Energie zonnepanelen"),
    "grid_import_energy": ("Grid import energy", "Afgenomen energie"),
    "grid_export_energy": ("Grid export energy", "Geïnjecteerde energie"),
    "battery_charge_energy": ("Battery charged energy", "Energie in batterij"),
    "battery_discharge_energy": ("Battery discharged energy", "Energie uit batterij"),
    "solar_to_home_energy": ("Solar used directly", "Zonne-energie direct verbruikt"),
    "battery_to_home_energy": ("Battery used by home", "Batterij-energie verbruikt"),
    "grid_to_home_energy": ("Grid used by home", "Netstroom verbruikt"),
    "house_today": ("House energy today", "Energie huis vandaag"),
    "heat_pump_today": ("Heat pump energy today", "Energie warmtepomp vandaag"),
    "ev_today": ("Car charger energy today", "Energie laadpaal vandaag"),
    "solar_today": ("Solar energy today", "Zonne-energie vandaag"),
    "grid_import_today": ("Grid import today", "Afname vandaag"),
    "grid_export_today": ("Grid export today", "Injectie vandaag"),
    "self_sufficiency_today": ("Self-sufficiency today", "Zelfvoorziening vandaag"),
    "self_consumption_today": ("Self-consumption today", "Eigen verbruik vandaag"),
    "import_cost": ("Import cost", "Kosten afname"),
    "export_revenue": ("Export revenue", "Opbrengst injectie"),
    "heat_pump_cost": ("Heat pump cost", "Kosten warmtepomp"),
    "ev_cost": ("Car charging cost", "Kosten laden auto"),
    "net_cost_today": ("Net cost today", "Netto kosten vandaag"),
    "heat_pump_cost_today": ("Heat pump cost today", "Kosten warmtepomp vandaag"),
    "ev_cost_today": ("Car charging cost today", "Kosten laden auto vandaag"),
    "other_cost_today": ("Other consumers cost today", "Kosten overige verbruikers vandaag"),
}

TEXT = {
    "en": {
        "title": "Home Energy Monitor",
        "description": "Pick the sensors for your installation. Only the grid sensor is required; leave anything you don't have empty.",
        "errors": {
            "duplicate_sensor": "This sensor is already used for another field.",
            "export_without_import": "Set an import price sensor too.",
        },
        "abort": {"single_instance_allowed": "Home Energy Monitor is already set up."},
    },
    "nl": {
        "title": "Home Energy Monitor",
        "description": "Kies de sensoren van je installatie. Alleen de netsensor is verplicht; laat leeg wat je niet hebt.",
        "errors": {
            "duplicate_sensor": "Deze sensor wordt al voor een ander veld gebruikt.",
            "export_without_import": "Stel ook een afnameprijs-sensor in.",
        },
        "abort": {"single_instance_allowed": "Home Energy Monitor is al ingesteld."},
    },
}


def build(lang: str) -> dict:
    i = 0 if lang == "en" else 2
    t = TEXT[lang]
    step = {
        "title": t["title"],
        "description": t["description"],
        "data": {k: v[i] for k, v in FIELDS.items()},
        "data_description": {k: v[i + 1] for k, v in FIELDS.items()},
    }
    return {
        "config": {"step": {"user": step}, "error": t["errors"], "abort": t["abort"]},
        "options": {"step": {"init": step}, "error": t["errors"]},
        "entity": {
            "sensor": {
                k: {"name": v[0 if lang == "en" else 1]} for k, v in ENTITIES.items()
            }
        },
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in ("en", "nl"):
        (OUT / f"{lang}.json").write_text(
            json.dumps(build(lang), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print("written", list(OUT.iterdir()))
