"""
Mod and .pc file discovery for both extracted folders and zip archives.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import json_utils
from parser import parse_pc
from generator import validate


@dataclass
class ConfigEntry:
    pc_path: str
    info_path: Optional[str]
    status: str                  # "ok" | "bad" | "missing"
    source: str                  # "folder" | "zip"
    source_path: str             # zip file path or mod root folder
    pc_content: dict
    info_content: Optional[dict]  # parsed dict, {} if parse failed, None if missing
    info_raw: Optional[str]       # raw file text; None if file doesn't exist
    missing_fields: list
    config_name: str
    auto_detected: dict
    thumbnail: Optional[bytes] = None


def _info_config_path(pc_path: Path) -> Path:
    """Return the info_config path for a given .pc file.
    Tries all naming conventions used across different mods:
      info_config_{stem}.json  (standard BeamNG)
      info_{stem}.json         (some mods omit '_config_')
    Also strips a leading 'config_' from the pc stem if present.
    """
    stem = pc_path.stem
    candidates = [f"info_config_{stem}.json", f"info_{stem}.json"]
    if stem.lower().startswith("config_"):
        stripped = stem[len("config_"):]
        candidates += [f"info_config_{stripped}.json", f"info_{stripped}.json"]

    for name in candidates:
        p = pc_path.parent / name
        if p.exists():
            return p

    return pc_path.parent / candidates[0]  # fallback — caller checks existence


def _scan_folder_mod(mod_root: Path) -> list[ConfigEntry]:
    entries = []
    for root, _dirs, files in os.walk(mod_root):
        for fname in sorted(files):
            if not fname.endswith(".pc"):
                continue
            if fname.endswith(".bak") or ".bak." in fname:
                continue

            pc_path = Path(root) / fname
            config_name = pc_path.stem
            info_path = _info_config_path(pc_path)

            try:
                pc_content = json_utils.load_file(pc_path)
            except Exception:
                continue

            auto = parse_pc(pc_content)

            thumbnail = None
            for ext in ('.jpg', '.jpeg', '.png'):
                img_path = pc_path.with_suffix(ext)
                if img_path.exists():
                    try:
                        thumbnail = img_path.read_bytes()
                    except Exception:
                        pass
                    break

            if info_path.exists():
                raw_bytes = info_path.read_bytes()
                info_raw = json_utils.decode(raw_bytes)
                try:
                    info_content = json_utils.loads(info_raw)
                except Exception:
                    info_content = {}
                missing = validate(info_content)
                status = "ok" if not missing else "bad"
            else:
                info_raw     = None
                info_content = None
                missing      = []
                status       = "missing"

            entries.append(ConfigEntry(
                pc_path=str(pc_path),
                info_path=str(info_path) if info_content is not None else None,
                status=status,
                source="folder",
                source_path=str(mod_root),
                pc_content=pc_content,
                info_content=info_content,
                info_raw=info_raw,
                missing_fields=missing,
                config_name=config_name,
                auto_detected=auto,
                thumbnail=thumbnail,
            ))

    return entries


def scan_mods_folder(mods_path: str) -> dict[str, list[ConfigEntry]]:
    """
    Scan a folder containing mods (zips and/or subfolders).
    Returns {mod_display_name: [ConfigEntry, ...]} — only mods with at least one .pc.
    """
    from zip_handler import scan_zip

    result: dict[str, list[ConfigEntry]] = {}
    mods_root = Path(mods_path)

    for item in sorted(mods_root.iterdir()):
        if item.suffix.lower() == ".zip":
            entries = scan_zip(item)
            if entries:
                result[item.name] = entries
        elif item.is_dir():
            entries = _scan_folder_mod(item)
            if entries:
                result[item.name] = entries

    return result
