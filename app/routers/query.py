from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.database import db_session
from app.schemas import (
    ConocimientoImportRequest,
    ConocimientoManualRequest,
    ConsultaRequest,
    FeedbackRequest,
    ParoManualRequest,
)
from app.services.query_service import build_consulta_response


router = APIRouter(tags=["consulta"])


@router.post("/consulta")
def consulta(payload: ConsultaRequest):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        return build_consulta_response(
            connection,
            settings,
            consulta=payload.consulta,
            top_k=payload.top_k,
            usar_llm=payload.usar_llm,
            provider=payload.provider,
            zona=payload.zona,
            contexto_extra=payload.contexto_extra,
        )


@router.post("/paro")
def registrar_paro(payload: ParoManualRequest):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        connection.execute(
            """
            INSERT INTO paros_dds (
                fuente_archivo, mes, dia, fecha, turno, componente, descripcion,
                num_paros, tiempo_min, causa_basica, accion_inmediata,
                accion_sistematica, formato, absorcion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "registro_manual",
                payload.fecha[:7] if payload.fecha else None,
                None,
                payload.fecha,
                payload.turno,
                payload.componente,
                payload.descripcion,
                payload.num_paros,
                payload.tiempo_min,
                payload.causa_basica,
                payload.accion_inmediata,
                payload.accion_sistematica,
                payload.formato,
                payload.absorcion,
            ),
        )
        return {"estado": "ok"}


@router.post("/feedback")
def guardar_feedback(payload: FeedbackRequest):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        connection.execute(
            """
            INSERT INTO feedback (consulta, respuesta_ia, funciono, comentario)
            VALUES (?, ?, ?, ?)
            """,
            (
                payload.consulta,
                payload.respuesta_ia,
                payload.funciono,
                payload.comentario,
            ),
        )
        return {"estado": "ok"}


@router.post("/conocimiento")
def guardar_conocimiento(payload: ConocimientoManualRequest):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        connection.execute(
            """
            INSERT INTO conocimiento_manual (
                area, estacion, componente, tipo, titulo, descripcion,
                solucion, causa_raiz, tags, fuente
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.area,
                payload.estacion,
                payload.componente,
                payload.tipo,
                payload.titulo,
                payload.descripcion,
                payload.solucion,
                payload.causa_raiz,
                payload.tags,
                payload.fuente,
            ),
        )
        return {"estado": "ok"}


@router.post("/conocimiento/import")
def importar_conocimiento(payload: ConocimientoImportRequest):
    settings = get_settings()
    insertados = 0
    omitidos = 0

    with db_session(settings.db_path) as connection:
        for item in payload.items:
            existente = connection.execute(
                """
                SELECT 1
                FROM conocimiento_manual
                WHERE
                    LOWER(COALESCE(area, '')) = LOWER(COALESCE(?, ''))
                    AND LOWER(COALESCE(estacion, '')) = LOWER(COALESCE(?, ''))
                    AND LOWER(COALESCE(componente, '')) = LOWER(COALESCE(?, ''))
                    AND LOWER(COALESCE(titulo, '')) = LOWER(COALESCE(?, ''))
                    AND LOWER(COALESCE(descripcion, '')) = LOWER(COALESCE(?, ''))
                LIMIT 1
                """,
                (
                    item.area,
                    item.estacion,
                    item.componente,
                    item.titulo,
                    item.descripcion,
                ),
            ).fetchone()

            if existente:
                omitidos += 1
                continue

            connection.execute(
                """
                INSERT INTO conocimiento_manual (
                    area, estacion, componente, tipo, titulo, descripcion,
                    solucion, causa_raiz, tags, fuente
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.area,
                    item.estacion,
                    item.componente,
                    item.tipo,
                    item.titulo,
                    item.descripcion,
                    item.solucion,
                    item.causa_raiz,
                    item.tags,
                    item.fuente,
                ),
            )
            insertados += 1

    return {"estado": "ok", "insertados": insertados, "omitidos": omitidos}
