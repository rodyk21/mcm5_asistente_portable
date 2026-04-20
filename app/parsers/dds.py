from __future__ import annotations

from pathlib import Path

from app.parsers.base import ParsedDocument, open_workbook
from app.utils import (
    build_iso_date,
    extract_month_from_name,
    extract_year_from_path,
    looks_like_day_sheet,
    normalize_text,
    parse_float,
    parse_int,
    slug_text,
)


HEADER_MAP = {
    "turno": "turno",
    "componente": "componente",
    "descripcion": "descripcion",
    "paros": "num_paros",
    "tiempo paro": "tiempo_min",
    "causa basica": "causa_basica",
    "accion inmediata": "accion_inmediata",
    "accion sistematica": "accion_sistematica",
}

HEADER_TEXTS = {
    "turno",
    "componente",
    "descripcion del problema rdi",
    "paros [#]",
    "tiempo paro [min]",
    "causa basica",
    "accion inmediata",
    "accion sistematica",
    "nombre",
    "comentarios",
    "autocausa",
    "fin turno",
}


def _sheet_matrix(ws, max_row: int = 450, max_col: int = 39) -> list[tuple[object, ...]]:
    return list(ws.iter_rows(min_row=1, max_row=min(ws.max_row, max_row), max_col=max_col, values_only=True))


def _value(matrix: list[tuple[object, ...]], row_index: int, col_index: int) -> object:
    if row_index < 1 or col_index < 1:
        return None
    try:
        row = matrix[row_index - 1]
    except IndexError:
        return None
    if col_index > len(row):
        return None
    return row[col_index - 1]


def _detect_header_columns(row: tuple[object, ...], max_col: int = 39) -> dict[str, int]:
    columns: dict[str, int] = {}
    for col in range(1, min(len(row), max_col) + 1):
        value = slug_text(row[col - 1])
        for token, field_name in HEADER_MAP.items():
            if token in value and field_name not in columns:
                columns[field_name] = col
    return columns


def _find_header_rows(matrix: list[tuple[object, ...]], max_col: int = 39) -> list[int]:
    rows: list[int] = []
    for row_index, row in enumerate(matrix, start=1):
        values = [slug_text(value) for value in row[:max_col]]
        if (
            any("turno" in value for value in values)
            and any("componente" in value for value in values)
            and any("descripcion" in value for value in values)
        ):
            rows.append(row_index)
    return rows


def _is_header_like_row(row: dict) -> bool:
    values = [
        slug_text(row.get("componente")),
        slug_text(row.get("descripcion")),
        slug_text(row.get("causa_basica")),
        slug_text(row.get("accion_inmediata")),
        slug_text(row.get("accion_sistematica")),
    ]
    return any(value in HEADER_TEXTS for value in values if value)


def _has_meaningful_dds_data(row: dict) -> bool:
    if _is_header_like_row(row):
        return False
    if row["descripcion"] and "why" in slug_text(row["descripcion"]):
        return False
    if row["causa_basica"] and row["causa_basica"].startswith("HAY ") and not any(
        [row["componente"], row["descripcion"], row["accion_inmediata"], row["accion_sistematica"]]
    ):
        return False
    has_context = any(
        [
            row["componente"],
            row["num_paros"] is not None,
            row["tiempo_min"] is not None,
            row["accion_inmediata"],
            row["accion_sistematica"],
        ]
    )
    return has_context and any(
        [
            row["descripcion"],
            row["componente"],
            row["accion_inmediata"],
            row["accion_sistematica"],
        ]
    )


def parse_dds(path: Path) -> ParsedDocument:
    parsed = ParsedDocument(tipo="DDS", source_path=path)
    workbook = open_workbook(path, read_only=True)
    month = extract_month_from_name(path.name)
    year = extract_year_from_path(path)

    try:
        for sheet_name in workbook.sheetnames:
            if not looks_like_day_sheet(sheet_name):
                continue

            ws = workbook[sheet_name]
            matrix = _sheet_matrix(ws)
            header_rows = _find_header_rows(matrix)
            if not header_rows:
                continue

            day = parse_int(sheet_name)
            fecha = build_iso_date(year, month, day)

            for index, header_row in enumerate(header_rows):
                columns = _detect_header_columns(matrix[header_row - 1])
                if not {"turno", "componente", "descripcion"}.issubset(columns):
                    continue

                stop_row = header_rows[index + 1] - 1 if index + 1 < len(header_rows) else len(matrix)
                empty_streak = 0
                data_started = False

                for row_index in range(header_row + 1, stop_row + 1):
                    raw = {field: _value(matrix, row_index, col) for field, col in columns.items()}
                    row = {
                        "fuente_archivo": str(path),
                        "mes": f"{year}-{month:02d}" if year and month else None,
                        "dia": day,
                        "fecha": fecha,
                        "turno": parse_int(raw.get("turno")),
                        "componente": normalize_text(raw.get("componente")) or None,
                        "descripcion": normalize_text(raw.get("descripcion")) or None,
                        "num_paros": parse_int(raw.get("num_paros")),
                        "tiempo_min": parse_float(raw.get("tiempo_min")),
                        "causa_basica": normalize_text(raw.get("causa_basica")) or None,
                        "accion_inmediata": normalize_text(raw.get("accion_inmediata")) or None,
                        "accion_sistematica": normalize_text(raw.get("accion_sistematica")) or None,
                        "formato": None,
                        "absorcion": None,
                    }

                    if not _has_meaningful_dds_data(row):
                        if data_started and not any(
                            [
                                row["turno"] is not None,
                                row["componente"],
                                row["descripcion"],
                                row["num_paros"] is not None,
                                row["tiempo_min"] is not None,
                                row["causa_basica"],
                                row["accion_inmediata"],
                                row["accion_sistematica"],
                            ]
                        ):
                            empty_streak += 1
                            if empty_streak >= 12:
                                break
                        continue

                    data_started = True
                    empty_streak = 0
                    parsed.add("paros_dds", row)
    finally:
        workbook.close()

    return parsed
