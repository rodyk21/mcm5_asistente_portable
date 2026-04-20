from __future__ import annotations

from pathlib import Path

from app.parsers.base import ParsedDocument, open_workbook
from app.utils import compact_join, normalize_text, parse_excel_date, to_json


def _read_chain_porques(ws) -> str:
    values: list[str] = []
    for row_index in range(10, min(ws.max_row, 25) + 1):
        for col in range(1, 20, 3):
            value = normalize_text(ws.cell(row_index, col).value)
            if value:
                values.append(value)
    return to_json(values)


def _read_preventive_actions(ws) -> str | None:
    lines: list[str] = []
    for row_index in range(32, 40):
        line = compact_join(ws.cell(row_index, col).value for col in range(1, 8))
        if line:
            lines.append(line)
    return "\n".join(lines) if lines else None


def parse_pm_card(path: Path) -> ParsedDocument:
    parsed = ParsedDocument(tipo="PM_CARD", source_path=path)
    workbook = open_workbook(path, read_only=True)

    try:
        ws = workbook["NEW PM Card"] if "NEW PM Card" in workbook.sheetnames else workbook[workbook.sheetnames[0]]
        porque_ws = workbook["Porque-Porque"] if "Porque-Porque" in workbook.sheetnames else None

        linea = normalize_text(ws["C4"].value)
        area = normalize_text(ws["E4"].value)
        parsed.add(
            "pm_cards",
            {
                "fuente_archivo": str(path),
                "fecha": parse_excel_date(ws["G2"].value),
                "linea": " / ".join(part for part in [linea, area] if part) or None,
                "zona": normalize_text(ws["C6"].value) or None,
                "subzona": normalize_text(ws["E6"].value) or None,
                "componente": normalize_text(ws["C7"].value) or None,
                "matricula_sap": normalize_text(ws["F7"].value) or None,
                "codigo_efecto": normalize_text(ws["D10"].value) or None,
                "descripcion_efecto": normalize_text(ws["B12"].value) or None,
                "codigo_accion": normalize_text(ws["D16"].value) or None,
                "descripcion_accion": normalize_text(ws["B18"].value) or None,
                "causa_basica": normalize_text(ws["B27"].value) or None,
                "piezas_utilizadas": normalize_text(ws["F26"].value) or None,
                "cadena_porques": _read_chain_porques(porque_ws) if porque_ws else to_json([]),
                "propuesta_mejora": normalize_text(ws["D40"].value) or None,
                "acciones_preventivas": _read_preventive_actions(ws),
            },
        )
    finally:
        workbook.close()

    return parsed
