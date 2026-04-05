"""
Analyze mods_data and report why configs may not appear in the dealer.
"""


def analyze(mods_data: dict) -> dict:
    """
    Returns {mod_name: [{config_name, critical: [...], warnings: [...]}]}
    Only mods/configs that have at least one issue are included.
    """
    result = {}
    for mod_name, entries in mods_data.items():
        mod_issues = []
        for entry in entries:
            critical = []
            warnings = []
            data = entry.info_content or {}

            if entry.status == "missing":
                critical.append("No info file")
            else:
                if not data.get("Configuration"):
                    critical.append("Configuration name is empty")
                if not data.get("Config Type"):
                    critical.append("Config Type is missing")
                if not data.get("Drivetrain"):
                    critical.append("Drivetrain is missing")
                if not data.get("Transmission"):
                    critical.append("Transmission is missing")
                if not data.get("Fuel Type"):
                    critical.append("Fuel Type is missing")
                try:
                    if not data.get("Value") or float(data["Value"]) <= 0:
                        critical.append("Value is missing or zero")
                except (TypeError, ValueError):
                    critical.append("Value is missing or zero")

                if not data.get("Description"):
                    warnings.append("No description set")
                if not data.get("Population"):
                    warnings.append("Population not set (won't spawn in traffic)")

                stats_missing = [k for k in ("Power", "Torque", "Weight")
                                 if not data.get(k)]
                if stats_missing:
                    warnings.append(f"Stats not filled: {', '.join(stats_missing)}")

                if entry.info_path:
                    from pathlib import Path
                    fname = Path(entry.info_path).name
                    if fname.startswith("info_config_"):
                        warnings.append("Legacy file name (info_config_*), should be info_*")

            if critical or warnings:
                mod_issues.append({
                    "config_name": entry.config_name,
                    "critical": critical,
                    "warnings": warnings,
                })

        if mod_issues:
            result[mod_name] = mod_issues

    return result
