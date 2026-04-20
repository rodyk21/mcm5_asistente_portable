from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable


MONTHS = {
    "enero": 1,
    "febrero": 2,
    "feb": 2,
    "marzo": 3,
    "març": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def slug_text(value: object) -> str:
    text = normalize_text(value).lower()
    text = (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def to_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def parse_excel_date(value: object) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        base = datetime(1899, 12, 30)
        try:
            return (base + timedelta(days=float(value))).date().isoformat()
        except OverflowError:
            return None
    text = normalize_text(value)
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def parse_int(value: object) -> int | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return int(float(text.replace(",", ".")))
    except ValueError:
        return None


def parse_float(value: object) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def extract_month_from_name(name: str) -> int | None:
    slug = slug_text(name)
    for token, month in MONTHS.items():
        if token in slug:
            return month
    return None


def extract_year_from_path(path: Path) -> int | None:
    for token in [path.name, *path.parts]:
        match = re.search(r"(20\d{2})", str(token))
        if match:
            return int(match.group(1))
    return None


def build_iso_date(year: int | None, month: int | None, day: int | None) -> str | None:
    if not year or not month or not day:
        return None
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def looks_like_variable_code(value: object) -> bool:
    return bool(re.fullmatch(r"\d{2,4}-\d{3}", normalize_text(value)))


def looks_like_day_sheet(name: str) -> bool:
    return normalize_text(name).isdigit()


def compact_join(values: Iterable[object], sep: str = " | ") -> str:
    items = [normalize_text(value) for value in values if normalize_text(value)]
    return sep.join(items)
