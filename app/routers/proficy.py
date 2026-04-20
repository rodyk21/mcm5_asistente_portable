from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.services.proficy import parse_proficy_file


router = APIRouter(prefix="/proficy", tags=["proficy"])


@router.post("/upload")
def proficy_upload(archivo: UploadFile = File(...)):
    settings = get_settings()
    filename = archivo.filename or "proficy"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".xls", ".xlsx", ".csv", ".txt"}:
        raise HTTPException(status_code=400, detail="Formato no soportado. Usa .xlsx, .csv, .txt o .xls.")

    temp_path = settings.uploads_dir / f"{uuid4().hex}_{Path(filename).name}"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(archivo.file, buffer)

    try:
        return parse_proficy_file(temp_path, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
