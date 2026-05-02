"""
Read and write files inside ZIP archives without extraction.
"""
import os
import shutil
import tempfile
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


def _zip_path(name: str) -> str:
    """Normalize a path for ZIP storage."""
    return name.replace("\\", "/").lstrip("/")


def _copy_zip_entry(src: zipfile.ZipFile, dst: zipfile.ZipFile, info: zipfile.ZipInfo):
    if info.is_dir():
        dst.mkdir(info)
        return

    with src.open(info, "r") as in_file:
        with dst.open(info, "w") as out_file:
            shutil.copyfileobj(in_file, out_file, length=1024 * 1024)


def write_many_to_zip(zip_path: str | Path, updates: dict[str, str]):
    """
    Add or replace many files inside a zip archive.

    Missing files are appended directly. Replacements are written through a
    temporary archive on disk, copying entries as streams so large mods are not
    loaded into RAM.
    """
    zip_path = Path(zip_path)
    normalized = {_zip_path(name): text.encode("utf-8") for name, text in updates.items()}
    if not normalized:
        return

    if not zip_path.exists():
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in normalized.items():
                zf.writestr(name, data)
        return

    with zipfile.ZipFile(zip_path, "r") as zf:
        existing_names = set(zf.namelist())

    if normalized.keys().isdisjoint(existing_names):
        with zipfile.ZipFile(zip_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in normalized.items():
                zf.writestr(name, data)
        return

    temp_name = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f"{zip_path.stem}.",
            suffix=".tmp.zip",
            dir=str(zip_path.parent),
        )
        os.close(fd)

        with zipfile.ZipFile(zip_path, "r") as src:
            with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as dst:
                for info in src.infolist():
                    if info.filename in normalized:
                        continue
                    _copy_zip_entry(src, dst, info)

                for name, data in normalized.items():
                    dst.writestr(name, data)

        os.replace(temp_name, zip_path)
        temp_name = None
    finally:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink(missing_ok=True)


def write_to_zip(zip_path: str, target_path_in_zip: str, content: str):
    """Backward-compatible single-file wrapper."""
    write_many_to_zip(zip_path, {target_path_in_zip: content})
