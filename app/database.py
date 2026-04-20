from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS paros_dds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_archivo TEXT,
    mes TEXT,
    dia INTEGER,
    fecha DATE,
    turno INTEGER,
    componente TEXT,
    descripcion TEXT,
    num_paros INTEGER,
    tiempo_min REAL,
    causa_basica TEXT,
    accion_inmediata TEXT,
    accion_sistematica TEXT,
    formato TEXT,
    absorcion TEXT,
    fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rdis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_archivo TEXT,
    fecha DATE,
    descripcion_problema TEXT,
    condiciones_incumplidas TEXT,
    cuando_empezo TEXT,
    maquina TEXT,
    redefinicion_problema TEXT,
    por_que_1 TEXT,
    por_que_2 TEXT,
    por_que_3 TEXT,
    por_que_4 TEXT,
    por_que_5 TEXT,
    causa_raiz TEXT,
    plan_accion TEXT,
    fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pm_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_archivo TEXT,
    fecha DATE,
    linea TEXT,
    zona TEXT,
    subzona TEXT,
    componente TEXT,
    matricula_sap TEXT,
    codigo_efecto TEXT,
    descripcion_efecto TEXT,
    codigo_accion TEXT,
    descripcion_accion TEXT,
    causa_basica TEXT,
    piezas_utilizadas TEXT,
    cadena_porques TEXT,
    propuesta_mejora TEXT,
    acciones_preventivas TEXT,
    fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mie_range (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_archivo TEXT,
    estacion TEXT,
    codigo_variable TEXT,
    descripcion TEXT,
    unidades TEXT,
    formato TEXT,
    valor_target TEXT,
    tolerancia_inf TEXT,
    tolerancia_sup TEXT,
    frecuencia_control TEXT,
    prioridad TEXT,
    tipo TEXT,
    fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mie_cambios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente_archivo TEXT,
    fecha DATE,
    autor TEXT,
    codigo_variable TEXT,
    descripcion_variable TEXT,
    valor_anterior TEXT,
    valor_actual TEXT,
    motivo TEXT,
    comentarios TEXT,
    fecha_ingesta DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS archivos_procesados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta_archivo TEXT UNIQUE,
    tipo TEXT,
    fecha_proceso DATETIME DEFAULT CURRENT_TIMESTAMP,
    registros_insertados INTEGER
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    consulta TEXT,
    respuesta_ia TEXT,
    funciono INTEGER,
    comentario TEXT
);

CREATE TABLE IF NOT EXISTS conocimiento_manual (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    area TEXT,
    estacion TEXT,
    componente TEXT,
    tipo TEXT,
    titulo TEXT,
    descripcion TEXT,
    solucion TEXT,
    causa_raiz TEXT,
    tags TEXT,
    fuente TEXT
);

CREATE INDEX IF NOT EXISTS idx_paros_dds_fecha ON paros_dds(fecha);
CREATE INDEX IF NOT EXISTS idx_paros_dds_componente ON paros_dds(componente);
CREATE INDEX IF NOT EXISTS idx_rdis_fecha ON rdis(fecha);
CREATE INDEX IF NOT EXISTS idx_pm_cards_fecha ON pm_cards(fecha);
CREATE INDEX IF NOT EXISTS idx_mie_range_codigo ON mie_range(codigo_variable);
CREATE INDEX IF NOT EXISTS idx_mie_cambios_codigo ON mie_cambios(codigo_variable);
CREATE INDEX IF NOT EXISTS idx_conocimiento_manual_componente ON conocimiento_manual(componente);
CREATE INDEX IF NOT EXISTS idx_conocimiento_manual_estacion ON conocimiento_manual(estacion);
"""


def get_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, check_same_thread=False, timeout=60)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    connection.execute("PRAGMA busy_timeout = 60000;")
    connection.execute("PRAGMA journal_mode = WAL;")
    connection.execute("PRAGMA synchronous = NORMAL;")
    return connection


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
        connection.commit()


@contextmanager
def db_session(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = get_connection(db_path)
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
