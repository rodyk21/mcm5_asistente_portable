from __future__ import annotations

from pathlib import Path

from app.parsers.base import ParsedDocument, first_text_in_row, open_workbook, row_text
from app.utils import normalize_text, parse_excel_date, to_json


def _extract_conditions(ws) -> str:
    rows = []
    for row_index in range(13, 22):
        condicion = normalize_text(ws[f"B{row_index}"].value)
        if not condicion:
            continue
        estado = ""
        if normalize_text(ws[f"R{row_index}"].value):
            estado = normalize_text(ws[f"R{row_index}"].value)
        elif normalize_text(ws[f"S{row_index}"].value):
            estado = normalize_text(ws[f"S{row_index}"].value)
        elif normalize_text(ws[f"T{row_index}"].value):
            estado = normalize_text(ws[f"T{row_index}"].value)
        comentario = normalize_text(ws[f"U{row_index}"].value)
        if estado or comentario:
            rows.append({"condicion": condicion, "estado": estado, "comentario": comentario})
    return to_json(rows)


def _extract_plan_action(ws) -> str | None:
    lines: list[str] = []
    for row_index in range(45, min(ws.max_row, 70) + 1):
        text = row_text(ws, row_index, start_col=1, end_col=35)
        if text:
            lines.append(text)
    return "\n".join(lines) if lines else None


def parse_rdi(path: Path) -> ParsedDocument:
    parsed = ParsedDocument(tipo="RDI", source_path=path)
    workbook = open_workbook(path, read_only=False)

    try:
        sheet_name = "RDI Electrónico" if "RDI Electrónico" in workbook.sheetnames else workbook.sheetnames[0]
        ws = workbook[sheet_name]

        parsed.add(
            "rdis",
            {
                "fuente_archivo": str(path),
                "fecha": parse_excel_date(ws["D3"].value),
                "descripcion_problema": normalize_text(ws["A6"].value) or None,
                "condiciones_incumplidas": _extract_conditions(ws),
                "cuando_empezo": first_text_in_row(
                    ws,
                    27,
                    start_col=1,
                    end_col=35,
                    skip_tokens=("cuando", "empezo", "normal", "arrancada"),
                ),
                "maquina": normalize_text(ws["Q3"].value) or None,
                "redefinicion_problema": first_text_in_row(
                    ws,
                    32,
                    start_col=1,
                    end_col=35,
                    skip_tokens=("redefinicion", "problema"),
                ),
                "por_que_1": row_text(ws, 36, start_col=1, end_col=35) or None,
                "por_que_2": row_text(ws, 37, start_col=1, end_col=35) or None,
                "por_que_3": row_text(ws, 38, start_col=1, end_col=35) or None,
                "por_que_4": row_text(ws, 39, start_col=1, end_col=35) or None,
                "por_que_5": row_text(ws, 40, start_col=1, end_col=35) or None,
                "causa_raiz": row_text(ws, 42, start_col=1, end_col=35) or None,
                "plan_accion": _extract_plan_action(ws),
            },
        )
    finally:
        workbook.close()

    return parsed
