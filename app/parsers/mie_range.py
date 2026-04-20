from __future__ import annotations

import re
from pathlib import Path

from app.parsers.base import ParsedDocument, find_row_by_keywords, open_workbook
from app.utils import looks_like_variable_code, normalize_text, parse_excel_date, slug_text


SETUP_SHEETS = ("set up settings", "setting de proceso")
VARIABLE_SHEETS = ("variables de control",)
CHANGE_SHEETS = ("cambios realizados",)


def _station_from_filename(path: Path) -> str:
    name = path.stem
    match = re.search(r"HMCM5[- ]\d+[- ](.+)$", name, flags=re.IGNORECASE)
    return normalize_text(match.group(1)) if match else normalize_text(name)


def _match_sheet(workbook, aliases: tuple[str, ...]) -> str | None:
    for sheet_name in workbook.sheetnames:
        if slug_text(sheet_name) in aliases:
            return sheet_name
    return None


def _find_header_row(ws) -> int | None:
    return find_row_by_keywords(
        ws,
        start_row=1,
        end_row=min(ws.max_row, 30),
        keywords=("descripcion", "tolerancia inferior", "tolerancia superior"),
        max_col=80,
    )


def _find_column(ws, row_range: range, matcher) -> int | None:
    for row_index in row_range:
        for col in range(1, 81):
            value = slug_text(ws.cell(row_index, col).value)
            if value and matcher(value):
                return col
    return None


def _detect_header_info(ws) -> tuple[int | None, dict[str, int], int | None]:
    header_row = _find_header_row(ws)
    if not header_row:
        return None, {}, None

    scan_rows = range(header_row, min(ws.max_row, header_row + 3) + 1)
    columns: dict[str, int] = {}
    columns["codigo"] = _find_column(ws, scan_rows, lambda value: value in {"n", "no"} or "numero" in value)
    columns["unidades"] = _find_column(ws, scan_rows, lambda value: "unidades" in value)
    columns["tol_inf"] = _find_column(ws, scan_rows, lambda value: "tolerancia inferior" in value)
    columns["tol_sup"] = _find_column(ws, scan_rows, lambda value: "tolerancia superior" in value)
    columns["frecuencia"] = _find_column(ws, scan_rows, lambda value: "frecuencia" in value)
    columns["prioridad"] = _find_column(ws, scan_rows, lambda value: "prioridad" in value or "q-related" in value)

    descripcion_candidates: list[int] = []
    for row_index in scan_rows:
        for col in range(1, 81):
            value = slug_text(ws.cell(row_index, col).value)
            if "descripcion" in value:
                descripcion_candidates.append(col)

    codigo_col = columns.get("codigo") or 1
    tol_inf_col = columns.get("tol_inf") or 81
    if descripcion_candidates:
        preferred = [col for col in descripcion_candidates if codigo_col < col < tol_inf_col]
        columns["descripcion"] = min(preferred or descripcion_candidates, key=lambda col: abs(col - codigo_col))

    if not columns.get("unidades") or not columns.get("tol_inf"):
        return header_row, columns, None

    format_row = None
    best_score = 0
    start_col = columns["unidades"] + 1
    end_col = columns["tol_inf"] - 1
    for row_index in range(header_row, min(ws.max_row, header_row + 4) + 1):
        score = sum(1 for col in range(start_col, end_col + 1) if normalize_text(ws.cell(row_index, col).value))
        if score > best_score:
            best_score = score
            format_row = row_index

    return header_row, columns, format_row


def _extract_range_rows(parsed: ParsedDocument, path: Path, ws, tipo: str) -> None:
    header_row, columns, format_row = _detect_header_info(ws)
    required = {"codigo", "descripcion", "unidades", "tol_inf", "tol_sup"}
    if not header_row or not format_row or not required.issubset(columns):
        return

    station = _station_from_filename(path)
    format_columns: list[tuple[int, str]] = []
    for col in range(columns["unidades"] + 1, columns["tol_inf"]):
        format_name = normalize_text(ws.cell(format_row, col).value)
        if format_name:
            format_columns.append((col, format_name))

    for row_index in range(format_row + 1, ws.max_row + 1):
        codigo = normalize_text(ws.cell(row_index, columns["codigo"]).value)
        if not looks_like_variable_code(codigo):
            continue

        descripcion = normalize_text(ws.cell(row_index, columns["descripcion"]).value) or None
        unidades = normalize_text(ws.cell(row_index, columns["unidades"]).value) or None
        tolerancia_inf = normalize_text(ws.cell(row_index, columns["tol_inf"]).value) or None
        tolerancia_sup = normalize_text(ws.cell(row_index, columns["tol_sup"]).value) or None
        frecuencia = (
            normalize_text(ws.cell(row_index, columns["frecuencia"]).value) if columns.get("frecuencia") else None
        )
        prioridad = (
            normalize_text(ws.cell(row_index, columns["prioridad"]).value) if columns.get("prioridad") else None
        )

        inserted_any = False
        for col, formato in format_columns:
            target_value = normalize_text(ws.cell(row_index, col).value)
            if not target_value:
                continue
            inserted_any = True
            parsed.add(
                "mie_range",
                {
                    "fuente_archivo": str(path),
                    "estacion": station,
                    "codigo_variable": codigo,
                    "descripcion": descripcion,
                    "unidades": unidades,
                    "formato": formato,
                    "valor_target": target_value,
                    "tolerancia_inf": tolerancia_inf,
                    "tolerancia_sup": tolerancia_sup,
                    "frecuencia_control": frecuencia,
                    "prioridad": prioridad,
                    "tipo": tipo,
                },
            )

        if not inserted_any:
            parsed.add(
                "mie_range",
                {
                    "fuente_archivo": str(path),
                    "estacion": station,
                    "codigo_variable": codigo,
                    "descripcion": descripcion,
                    "unidades": unidades,
                    "formato": None,
                    "valor_target": None,
                    "tolerancia_inf": tolerancia_inf,
                    "tolerancia_sup": tolerancia_sup,
                    "frecuencia_control": frecuencia,
                    "prioridad": prioridad,
                    "tipo": tipo,
                },
            )


def _extract_change_rows(parsed: ParsedDocument, path: Path, ws) -> None:
    header_row = find_row_by_keywords(
        ws,
        start_row=1,
        end_row=min(ws.max_row, 15),
        keywords=("fecha", "autor", "cambiado"),
        max_col=30,
    )
    if not header_row:
        return

    columns: dict[str, int] = {}
    for col in range(1, 20):
        value = slug_text(ws.cell(header_row, col).value)
        if "fecha" in value and "fecha" not in columns:
            columns["fecha"] = col
        elif "autor" in value and "autor" not in columns:
            columns["autor"] = col
        elif ("mr cambiado" in value or "cambiado" in value) and "codigo" not in columns:
            columns["codigo"] = col
        elif "concepto" in value and "descripcion" not in columns:
            columns["descripcion"] = col
        elif "anterior" in value and "anterior" not in columns:
            columns["anterior"] = col
        elif "actual" in value and "actual" not in columns:
            columns["actual"] = col
        elif "motivo" in value and "motivo" not in columns:
            columns["motivo"] = col
        elif "coment" in value and "comentarios" not in columns:
            columns["comentarios"] = col

    if not {"fecha", "autor", "codigo"}.issubset(columns):
        return

    def optional_value(row_index: int, key: str) -> str | None:
        column = columns.get(key)
        if not column:
            return None
        return normalize_text(ws.cell(row_index, column).value) or None

    blank_streak = 0
    for row_index in range(header_row + 1, ws.max_row + 1):
        codigo = normalize_text(ws.cell(row_index, columns["codigo"]).value)
        autor = normalize_text(ws.cell(row_index, columns["autor"]).value)
        fecha = ws.cell(row_index, columns["fecha"]).value

        if not codigo and not autor and not fecha:
            blank_streak += 1
            if blank_streak >= 15:
                break
            continue
        blank_streak = 0

        if not looks_like_variable_code(codigo):
            continue

        parsed.add(
            "mie_cambios",
            {
                "fuente_archivo": str(path),
                "fecha": parse_excel_date(fecha),
                "autor": autor or None,
                "codigo_variable": codigo,
                "descripcion_variable": optional_value(row_index, "descripcion"),
                "valor_anterior": optional_value(row_index, "anterior"),
                "valor_actual": optional_value(row_index, "actual"),
                "motivo": optional_value(row_index, "motivo"),
                "comentarios": optional_value(row_index, "comentarios"),
            },
        )


def parse_mie_range(path: Path) -> ParsedDocument:
    parsed = ParsedDocument(tipo="MIE_RANGE", source_path=path)
    workbook = open_workbook(path, read_only=False)

    try:
        setup_sheet = _match_sheet(workbook, SETUP_SHEETS)
        variable_sheet = _match_sheet(workbook, VARIABLE_SHEETS)
        change_sheet = _match_sheet(workbook, CHANGE_SHEETS)

        if setup_sheet:
            _extract_range_rows(parsed, path, workbook[setup_sheet], "setup")
        if variable_sheet:
            _extract_range_rows(parsed, path, workbook[variable_sheet], "variable_control")
        if change_sheet:
            _extract_change_rows(parsed, path, workbook[change_sheet])
    finally:
        workbook.close()

    return parsed
