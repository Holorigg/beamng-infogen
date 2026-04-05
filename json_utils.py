"""
Tolerant JSON reader for BeamNG mod files.
Handles: trailing commas, missing commas between fields, UTF-8 BOM, cp1251 fallback.
"""
import json
import re
from pathlib import Path


def loads(text: str) -> dict:
    """Parse JSON text, tolerating trailing commas and missing commas between fields."""
    text = text.lstrip("\ufeff")                        # strip BOM if any
    text = re.sub(r",(\s*[}\]])", r"\1", text)          # remove trailing commas
    # Add missing commas: line ending with a value followed by next key on a new line
    text = re.sub(r'("|\d|true|false|null)([ \t]*\n[ \t]*")', r'\1,\2', text)
    return json.loads(text)


def decode(raw: bytes) -> str:
    """Decode bytes to string: UTF-8-sig first, cp1251 fallback."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace")


def load_bytes(raw: bytes) -> dict:
    """Decode bytes then parse tolerantly."""
    return loads(decode(raw))


def load_file(path) -> dict:
    """Read a file from disk and parse tolerantly."""
    return load_bytes(Path(path).read_bytes())
