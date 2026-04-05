"""
Read and write files inside ZIP archives without extraction.
"""
import io
import zipfile
from pathlib import Path

import json_utils


def scan_zip(zip_path: Path) -> list:
    """
    Scan a zip for .pc configs and their info_config json files.
    Returns list of ConfigEntry objects (imported locally to avoid circular import).
    """
    from scanner import ConfigEntry
    from parser import parse_pc
    from generator import validate

    entries = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names_set = set(zf.namelist())

            pc_files = [
                n for n in names_set
                if n.endswith(".pc") and not n.endswith(".bak") and not n.endswith(".bak.pc")
            ]

            for pc_zip_path in pc_files:
                config_name = Path(pc_zip_path).stem
                pc_dir      = Path(pc_zip_path).parent  # keep as Path to avoid "./" prefix

                def _zp(filename: str) -> str:
                    """Build a zip-safe path (no leading './')."""
                    p = (pc_dir / filename).as_posix()
                    return p.lstrip("./") if p.startswith("./") else p

                names = [
                    f"info_config_{config_name}.json",
                    f"info_{config_name}.json",
                ]
                if config_name.lower().startswith("config_"):
                    stripped = config_name[len("config_"):]
                    names += [f"info_config_{stripped}.json", f"info_{stripped}.json"]

                candidates = [_zp(n) for n in names]
                info_zip_path = next((c for c in candidates if c in names_set), candidates[0])

                try:
                    pc_content = json_utils.load_bytes(zf.read(pc_zip_path))
                except Exception:
                    continue

                from parser import parse_pc as _parse
                auto = _parse(pc_content)

                thumbnail = None
                for ext in ('.jpg', '.jpeg', '.png'):
                    img_zip_path = _zp(f"{config_name}{ext}")
                    if img_zip_path in names_set:
                        try:
                            thumbnail = zf.read(img_zip_path)
                        except Exception:
                            pass
                        break

                if info_zip_path in names_set:
                    raw_bytes = zf.read(info_zip_path)
                    info_raw  = json_utils.decode(raw_bytes)
                    try:
                        info_content = json_utils.loads(info_raw)
                    except Exception:
                        info_content = {}
                    missing = validate(info_content)
                    status  = "ok" if not missing else "bad"
                else:
                    info_raw     = None
                    info_content = None
                    missing      = []
                    status       = "missing"

                entries.append(ConfigEntry(
                    pc_path=pc_zip_path,
                    info_path=info_zip_path if info_content is not None else None,
                    status=status,
                    source="zip",
                    source_path=str(zip_path),
                    pc_content=pc_content,
                    info_content=info_content,
                    info_raw=info_raw,
                    missing_fields=missing,
                    config_name=config_name,
                    auto_detected=auto,
                    thumbnail=thumbnail,
                ))

    except (zipfile.BadZipFile, OSError):
        pass

    return entries


def write_to_zip(zip_path: str, target_path_in_zip: str, content: str):
    """
    Add or replace a file inside a zip archive.
    Reads all entries into memory, updates the target, writes the zip back.
    """
    zip_path = Path(zip_path)
    target = target_path_in_zip.replace("\\", "/")

    existing: dict[str, bytes] = {}
    if zip_path.exists():
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for name in zf.namelist():
                    existing[name] = zf.read(name)
        except zipfile.BadZipFile:
            pass

    existing[target] = content.encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in existing.items():
            zf.writestr(name, data)

    zip_path.write_bytes(buf.getvalue())
