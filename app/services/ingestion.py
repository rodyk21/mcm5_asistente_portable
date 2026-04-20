from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from app.config import Settings
from app.database import init_db
from app.parsers.dds import parse_dds
from app.parsers.mie_range import parse_mie_range
from app.parsers.pm_card import parse_pm_card
from app.parsers.rdi import parse_rdi
from app.utils import normalize_text, slug_text


PARSERS = {
    "DDS": parse_dds,
    "RDI": parse_rdi,
    "PM_CARD": parse_pm_card,
    "MIE_RANGE": parse_mie_range,
}

SUPPORTED_TYPES = tuple(PARSERS.keys())
logger = logging.getLogger(__name__)


def setup_database(settings: Settings) -> None:
    init_db(settings.db_path)


def should_skip_path(path: Path, settings: Settings) -> bool:
    full_slug = slug_text(str(path))
    name_slug = slug_text(path.name)
    if not path.is_file():
        return True
    if path.suffix.lower() not in {".xlsx", ".xlsm"}:
        return True
    if any(token in full_slug for token in settings.excluded_tokens):
        return True
    if any(token in name_slug for token in settings.excluded_tokens):
        return True
    return False


def iter_source_files(source_dir: Path, settings: Settings) -> Iterable[Path]:
    if not source_dir.exists():
        return []
    files = [path for path in source_dir.rglob("*") if not should_skip_path(path, settings)]
    return sorted(files)


def infer_document_type(path: Path, settings: Settings) -> str | None:
    full = path.resolve()
    try:
        if settings.dds_dir in full.parents:
            return "DDS"
        if settings.rdi_dir in full.parents:
            return "RDI"
        if settings.pm_dir in full.parents:
            return "PM_CARD"
        if settings.mie_dir in full.parents:
            return "MIE_RANGE"
    except FileNotFoundError:
        return None
    return None


def is_file_already_processed(connection, path: Path) -> bool:
    row = connection.execute(
        "SELECT 1 FROM archivos_procesados WHERE ruta_archivo = ?",
        (str(path.resolve()),),
    ).fetchone()
    return row is not None


def insert_rows(connection, table_name: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
    connection.executemany(sql, [tuple(row.get(column) for column in columns) for row in rows])
    return len(rows)


def process_single_file(connection, path: Path, doc_type: str, force: bool = False) -> dict:
    if not force and is_file_already_processed(connection, path):
        return {
            "archivo": str(path),
            "tipo": doc_type,
            "estado": "omitido",
            "motivo": "ya procesado",
            "registros": 0,
        }

    logger.info("Procesando %s como %s", path, doc_type)
    try:
        parsed = PARSERS[doc_type](path)
        inserted = 0
        for table_name, rows in parsed.tables.items():
            inserted += insert_rows(connection, table_name, rows)

        connection.execute(
            """
            INSERT INTO archivos_procesados (ruta_archivo, tipo, registros_insertados)
            VALUES (?, ?, ?)
            ON CONFLICT(ruta_archivo) DO UPDATE SET
                tipo = excluded.tipo,
                fecha_proceso = CURRENT_TIMESTAMP,
                registros_insertados = excluded.registros_insertados
            """,
            (str(path.resolve()), doc_type, inserted),
        )
        logger.info("Archivo %s procesado con %s registros", path, inserted)
        return {"archivo": str(path), "tipo": doc_type, "estado": "procesado", "registros": inserted}
    except Exception as exc:
        logger.exception("Fallo procesando %s", path)
        return {
            "archivo": str(path),
            "tipo": doc_type,
            "estado": "error",
            "motivo": normalize_text(exc) or exc.__class__.__name__,
            "registros": 0,
        }


def process_uploaded_file(connection, path: Path, doc_type: str) -> dict:
    return process_single_file(connection, path, doc_type, force=True)


def process_all_sources(connection, settings: Settings, force: bool = False) -> dict:
    summary = {"procesados": 0, "omitidos": 0, "registros": 0, "detalle": []}
    source_map = {
        "DDS": settings.dds_dir,
        "RDI": settings.rdi_dir,
        "PM_CARD": settings.pm_dir,
        "MIE_RANGE": settings.mie_dir,
    }

    for doc_type, source_dir in source_map.items():
        for path in iter_source_files(source_dir, settings):
            result = process_single_file(connection, path, doc_type, force=force)
            summary["detalle"].append(result)
            if result["estado"] == "procesado":
                summary["procesados"] += 1
                summary["registros"] += result["registros"]
            else:
                summary["omitidos"] += 1

    return summary
