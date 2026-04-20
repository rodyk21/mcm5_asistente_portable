from __future__ import annotations

from pydantic import BaseModel, Field


class IngestFolderRequest(BaseModel):
    force: bool = False


class IngestFileRequest(BaseModel):
    path: str
    force: bool = False


class ConsultaRequest(BaseModel):
    consulta: str = Field(..., min_length=3)
    top_k: int = 8
    usar_llm: bool = True
    provider: str | None = None
    zona: str | None = None
    contexto_extra: str | None = None


class ParoManualRequest(BaseModel):
    fecha: str | None = None
    turno: int | None = None
    componente: str
    descripcion: str
    num_paros: int = 1
    tiempo_min: float | None = None
    causa_basica: str | None = None
    accion_inmediata: str | None = None
    accion_sistematica: str | None = None
    formato: str | None = None
    absorcion: str | None = None


class FeedbackRequest(BaseModel):
    consulta: str
    respuesta_ia: str
    funciono: int
    comentario: str | None = None


class ConocimientoManualRequest(BaseModel):
    area: str | None = None
    estacion: str | None = None
    componente: str | None = None
    tipo: str = "foco_manual"
    titulo: str
    descripcion: str
    solucion: str | None = None
    causa_raiz: str | None = None
    tags: str | None = None
    fuente: str | None = "usuario"


class ConocimientoImportRequest(BaseModel):
    items: list[ConocimientoManualRequest] = Field(default_factory=list)
