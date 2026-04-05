"""
info_config JSON generation and validation.
"""
import random

_DESC_TEMPLATES = [
    "A well-rounded configuration suited for everyday driving.",
    "A capable variant offering a balanced blend of performance and comfort.",
    "Designed for those who demand reliability without sacrificing style.",
    "A versatile setup ready for both city streets and open highways.",
    "This configuration delivers a confident driving experience across all conditions.",
    "An accessible variant with a focus on practicality and dependability.",
    "Built for drivers who value smooth performance and long-distance comfort.",
    "A solid choice for anyone looking for a dependable daily driver.",
]


def _default_description() -> str:
    return random.choice(_DESC_TEMPLATES)

REQUIRED_FIELDS = ["Value", "Config Type", "Configuration", "Drivetrain", "Transmission", "Fuel Type"]


def validate(data: dict) -> list[str]:
    """Returns list of missing or invalid required field names."""
    missing = []
    for f in REQUIRED_FIELDS:
        if f not in data:
            missing.append(f)
        elif f == "Value":
            try:
                if float(data[f]) <= 0:
                    missing.append(f)
            except (TypeError, ValueError):
                missing.append(f)
        elif not data[f] and data[f] != 0:
            missing.append(f)
    return missing


def generate(config_name: str, auto_detected: dict, defaults: dict) -> dict:
    """Build a new info_config dict from auto-detection + user defaults."""
    data = {
        "Configuration":  config_name,
        "Config Type":    defaults.get("config_type", "Factory"),
        "Drivetrain":     auto_detected.get("Drivetrain",   "RWD"),
        "Transmission":   auto_detected.get("Transmission", "Automatic"),
        "Fuel Type":      auto_detected.get("Fuel Type",    "Gasoline"),
        "Propulsion":     "Electric" if auto_detected.get("Fuel Type") == "Electric" else "ICE",
        "Induction Type": defaults.get("induction", "Turbo"),
        "Body Style":     defaults.get("body_style", "Sedan"),
        "Value":          _random_price(defaults),
        "Population":     5000,
        "Off-Road Score": 20,
        "Description":    defaults.get("description") or _default_description(),
    }
    _apply_stats(data, defaults)
    return data


def fix(existing: dict, config_name: str, auto_detected: dict, defaults: dict) -> dict:
    """Add only missing required fields; leave all existing fields untouched."""
    result = dict(existing)
    if not result.get("Configuration"):
        result["Configuration"] = config_name
    if not result.get("Config Type"):
        result["Config Type"] = defaults.get("config_type", "Factory")
    if not result.get("Drivetrain"):
        result["Drivetrain"] = auto_detected.get("Drivetrain", "RWD")
    if not result.get("Transmission"):
        result["Transmission"] = auto_detected.get("Transmission", "Automatic")
    if not result.get("Fuel Type"):
        result["Fuel Type"] = auto_detected.get("Fuel Type", "Gasoline")
    try:
        if not result.get("Value") or float(result["Value"]) <= 0:
            result["Value"] = _random_price(defaults)
    except (TypeError, ValueError):
        result["Value"] = _random_price(defaults)
    return result


def _random_price(defaults: dict) -> int:
    try:
        lo = int(defaults.get("price_min", 10000))
        hi = int(defaults.get("price_max", 50000))
    except (ValueError, TypeError):
        lo, hi = 10000, 50000
    if lo > hi:
        lo, hi = hi, lo
    return round(random.randint(lo, hi) / 500) * 500


def _apply_stats(data: dict, defaults: dict):
    for key, dkey in [("Power", "power"), ("Torque", "torque"), ("Weight", "weight")]:
        val = defaults.get(dkey, "")
        try:
            data[key] = int(val)
        except (ValueError, TypeError):
            pass
