from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import get_settings
from app.database import db_session
from app.schemas import IngestFileRequest, IngestFolderRequest
from app.services.ingestion import (
    SUPPORTED_TYPES,
    infer_document_type,
    process_all_sources,
    process_single_file,
    process_uploaded_file,
    setup_database,
)


router = APIRouter(prefix="/ingest", tags=["ingesta"])


@router.post("/carpeta")
def ingest_folder(payload: IngestFolderRequest):
    settings = get_settings()
    setup_database(settings)
    with db_session(settings.db_path) as connection:
        return process_all_sources(connection, settings, force=payload.force)


@router.post("/archivo")
def ingest_file(payload: IngestFileRequest):
    settings = get_settings()
    setup_database(settings)
    path = Path(payload.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    doc_type = infer_document_type(path, settings)
    if not doc_type:
        raise HTTPException(status_code=400, detail="No se pudo inferir el tipo de documento desde la ruta")

    with db_session(settings.db_path) as connection:
        return process_single_file(connection, path, doc_type, force=payload.force)


@router.post("/upload")
def ingest_upload(
    tipo: str = Form(...),
    archivo: UploadFile = File(...),
):
    settings = get_settings()
    setup_database(settings)

    normalized_type = tipo.strip().upper()
    if normalized_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo no soportado. Usa uno de: {', '.join(SUPPORTED_TYPES)}",
        )

    suffix = Path(archivo.filename or "").suffix.lower()
    if suffix not in {".xlsx", ".xlsm"}:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .xlsx o .xlsm")

    temp_path = settings.uploads_dir / f"{uuid4().hex}_{Path(archivo.filename or 'archivo').name}"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    try:
        with db_session(settings.db_path) as connection:
            result = process_uploaded_file(connection, temp_path, normalized_type)
        result["nombre_original"] = archivo.filename
        return result
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
