from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import get_settings
from app.database import db_session
from app.services.document_library import search_library


router = APIRouter(tags=["datos"])


def _fetch_all(connection, sql: str, params: tuple) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, params).fetchall()]


@router.get("/paros")
def list_paros(
    componente: str | None = None,
    turno: int | None = None,
    fecha_desde: str | None = None,
    fecha_hasta: str | None = None,
    causa: str | None = None,
    limit: int = Query(default=100, le=500),
):
    settings = get_settings()
    clauses = []
    params = []
    if componente:
        clauses.append("LOWER(componente) LIKE ?")
        params.append(f"%{componente.lower()}%")
    if turno:
        clauses.append("turno = ?")
        params.append(turno)
    if fecha_desde:
        clauses.append("fecha >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        clauses.append("fecha <= ?")
        params.append(fecha_hasta)
    if causa:
        clauses.append("LOWER(causa_basica) LIKE ?")
        params.append(f"%{causa.lower()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM paros_dds {where} ORDER BY fecha DESC, id DESC LIMIT ?"
    params.append(limit)
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, sql, tuple(params))


@router.get("/rdis")
def list_rdis(limit: int = Query(default=100, le=500)):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, "SELECT * FROM rdis ORDER BY fecha DESC, id DESC LIMIT ?", (limit,))


@router.get("/pm_cards")
def list_pm_cards(limit: int = Query(default=100, le=500)):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, "SELECT * FROM pm_cards ORDER BY fecha DESC, id DESC LIMIT ?", (limit,))


@router.get("/mie_range")
def list_mie_range(
    estacion: str | None = None,
    codigo: str | None = None,
    formato: str | None = None,
    tipo: str | None = None,
    limit: int = Query(default=200, le=1000),
):
    settings = get_settings()
    clauses = []
    params = []
    if estacion:
        clauses.append("LOWER(estacion) LIKE ?")
        params.append(f"%{estacion.lower()}%")
    if codigo:
        clauses.append("LOWER(codigo_variable) LIKE ?")
        params.append(f"%{codigo.lower()}%")
    if formato:
        clauses.append("LOWER(formato) LIKE ?")
        params.append(f"%{formato.lower()}%")
    if tipo:
        clauses.append("tipo = ?")
        params.append(tipo)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM mie_range {where} ORDER BY estacion, codigo_variable LIMIT ?"
    params.append(limit)
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, sql, tuple(params))


@router.get("/mie_busqueda")
def mie_busqueda(
    q: str,
    limit: int = Query(default=50, le=200),
):
    settings = get_settings()
    like = f"%{q.lower()}%"
    with db_session(settings.db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM mie_range
            WHERE
                LOWER(COALESCE(estacion, '')) LIKE ?
                OR LOWER(COALESCE(codigo_variable, '')) LIKE ?
                OR LOWER(COALESCE(descripcion, '')) LIKE ?
                OR LOWER(COALESCE(formato, '')) LIKE ?
            ORDER BY estacion, codigo_variable
            LIMIT ?
            """,
            (like, like, like, like, limit),
        ).fetchall()
        return [dict(row) for row in rows]


@router.get("/stats")
def stats():
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        return {
            "paros_dds": connection.execute("SELECT COUNT(*) AS total FROM paros_dds").fetchone()["total"],
            "rdis": connection.execute("SELECT COUNT(*) AS total FROM rdis").fetchone()["total"],
            "pm_cards": connection.execute("SELECT COUNT(*) AS total FROM pm_cards").fetchone()["total"],
            "mie_range": connection.execute("SELECT COUNT(*) AS total FROM mie_range").fetchone()["total"],
            "mie_cambios": connection.execute("SELECT COUNT(*) AS total FROM mie_cambios").fetchone()["total"],
            "conocimiento_manual": connection.execute("SELECT COUNT(*) AS total FROM conocimiento_manual").fetchone()["total"],
            "archivos_procesados": connection.execute("SELECT COUNT(*) AS total FROM archivos_procesados").fetchone()["total"],
        }


@router.get("/alertas")
def alertas(limit: int = Query(default=20, le=100)):
    settings = get_settings()
    with db_session(settings.db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                componente,
                COUNT(*) AS total_paros,
                ROUND(SUM(COALESCE(tiempo_min, 0)), 2) AS tiempo_total_min
            FROM paros_dds
            WHERE componente IS NOT NULL AND componente <> ''
            GROUP BY componente
            HAVING COUNT(*) >= 3
            ORDER BY total_paros DESC, tiempo_total_min DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


@router.get("/mie_cambios")
def list_mie_cambios(
    codigo: str | None = None,
    limit: int = Query(default=100, le=500),
):
    settings = get_settings()
    clauses = []
    params = []
    if codigo:
        clauses.append("LOWER(codigo_variable) LIKE ?")
        params.append(f"%{codigo.lower()}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM mie_cambios {where} ORDER BY fecha DESC, id DESC LIMIT ?"
    params.append(limit)
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, sql, tuple(params))


@router.get("/conocimiento")
def list_conocimiento(
    q: str | None = None,
    limit: int = Query(default=100, le=500),
):
    settings = get_settings()
    clauses = []
    params = []
    if q:
        like = f"%{q.lower()}%"
        clauses.append(
            "("
            "LOWER(COALESCE(area, '')) LIKE ? OR "
            "LOWER(COALESCE(estacion, '')) LIKE ? OR "
            "LOWER(COALESCE(componente, '')) LIKE ? OR "
            "LOWER(COALESCE(titulo, '')) LIKE ? OR "
            "LOWER(COALESCE(descripcion, '')) LIKE ? OR "
            "LOWER(COALESCE(solucion, '')) LIKE ? OR "
            "LOWER(COALESCE(causa_raiz, '')) LIKE ? OR "
            "LOWER(COALESCE(tags, '')) LIKE ?"
            ")"
        )
        params.extend([like, like, like, like, like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM conocimiento_manual {where} ORDER BY fecha DESC, id DESC LIMIT ?"
    params.append(limit)
    with db_session(settings.db_path) as connection:
        return _fetch_all(connection, sql, tuple(params))


@router.get("/biblioteca")
def biblioteca(
    q: str = Query(default=""),
    limit: int = Query(default=50, le=200),
):
    settings = get_settings()
    return search_library(settings, q, limit=limit)
