from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

import requests

from app.config import Settings
from app.utils import normalize_text


TOKEN_RE = re.compile(r"[a-zA-Z0-9\-]{2,}")
SUPPORTED_PROVIDERS = ("auto", "anthropic", "openai", "google", "xai")


def _tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", normalize_text(text))
    normalized = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return [token.lower() for token in TOKEN_RE.findall(normalized)]


def _normalized_text(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(text or ""))
    return normalized.encode("ascii", "ignore").decode("ascii").lower()


def _score(query: str, text: str) -> float:
    query_tokens = _tokenize(query)
    text_tokens = _tokenize(text)
    if not query_tokens or not text_tokens:
        return 0.0
    query_counter = Counter(query_tokens)
    text_counter = Counter(text_tokens)
    intersection = sum(min(query_counter[token], text_counter[token]) for token in query_counter)
    return intersection / math.sqrt(len(query_tokens) * len(text_tokens))


def _score_rows(rows, consulta: str, builder, limit: int) -> list[dict]:
    scored = []
    for row in rows:
        haystack = builder(row)
        score = _score(consulta, haystack)
        if score > 0:
            item = dict(row)
            item["_score"] = score
            scored.append(item)
    scored.sort(key=lambda item: item["_score"], reverse=True)
    return scored[:limit]


def _filter_by_zone(items: list[dict], zone: str | None, fields: tuple[str, ...]) -> list[dict]:
    zone_slug = _normalized_text(zone)
    if not zone_slug:
        return items

    filtered = []
    for item in items:
        haystack = " ".join(_normalized_text(item.get(field)) for field in fields)
        if zone_slug in haystack:
            filtered.append(item)
    return filtered


def _summarize_counter(values: list[str], empty_message: str) -> str:
    normalized_values = [_normalized_text(value) for value in values if _normalized_text(value)]
    if not normalized_values:
        return empty_message
    value, count = Counter(normalized_values).most_common(1)[0]
    return f"{value} ({count})"


def _build_patterns(
    paros: list[dict],
    rdis: list[dict],
    pm_cards: list[dict],
    manual_knowledge: list[dict],
) -> list[str]:
    components = [item.get("componente") for item in paros]
    components.extend(item.get("componente") for item in pm_cards)
    causes = [item.get("causa_basica") for item in paros]
    causes.extend(item.get("causa_raiz") for item in rdis)
    causes.extend(item.get("causa_raiz") for item in manual_knowledge)
    solutions = [item.get("accion_inmediata") for item in paros]
    solutions.extend(item.get("descripcion_accion") for item in pm_cards)
    solutions.extend(item.get("solucion") for item in manual_knowledge)

    return [
        "Zona/componente mas repetido: " + _summarize_counter(components, "sin patron claro"),
        "Causa mas repetida: " + _summarize_counter(causes, "sin causa repetida clara"),
        "Solucion mas repetida: " + _summarize_counter(solutions, "sin solucion repetida clara"),
    ]


def _build_sources(
    paros: list[dict],
    rdis: list[dict],
    pm_cards: list[dict],
    mie: list[dict],
    feedback: list[dict],
    manual_knowledge: list[dict],
    parameter_details: dict,
) -> list[dict]:
    sources = [
        {"tipo": "DDS", "cantidad": len(paros), "detalle": "casos historicos similares"},
        {"tipo": "RDI", "cantidad": len(rdis), "detalle": "analisis y causa raiz"},
        {"tipo": "PM", "cantidad": len(pm_cards), "detalle": "intervenciones PM Card"},
        {"tipo": "MID_RANGE", "cantidad": len(mie), "detalle": "parametros relevantes"},
        {"tipo": "FEEDBACK", "cantidad": len(feedback), "detalle": "respuestas validadas"},
        {"tipo": "MANUAL", "cantidad": len(manual_knowledge), "detalle": "conocimiento manual"},
        {"tipo": "CAMBIOS_MR", "cantidad": len(parameter_details.get("cambios", [])), "detalle": "cambios recientes"},
    ]
    return [item for item in sources if item["cantidad"] > 0]


def find_similar_paros(connection, consulta: str, limit: int = 8) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM paros_dds
        ORDER BY fecha DESC, id DESC
        LIMIT 4000
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["componente"]),
                normalize_text(row["descripcion"]),
                normalize_text(row["causa_basica"]),
                normalize_text(row["accion_inmediata"]),
                normalize_text(row["accion_sistematica"]),
            ]
        ),
        limit,
    )


def find_related_rdis(connection, consulta: str, limit: int = 5) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM rdis
        ORDER BY fecha DESC, id DESC
        LIMIT 2000
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["descripcion_problema"]),
                normalize_text(row["redefinicion_problema"]),
                normalize_text(row["causa_raiz"]),
                normalize_text(row["plan_accion"]),
            ]
        ),
        limit,
    )


def find_related_pm_cards(connection, consulta: str, limit: int = 5) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM pm_cards
        ORDER BY fecha DESC, id DESC
        LIMIT 1000
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["componente"]),
                normalize_text(row["descripcion_efecto"]),
                normalize_text(row["descripcion_accion"]),
                normalize_text(row["causa_basica"]),
                normalize_text(row["propuesta_mejora"]),
            ]
        ),
        limit,
    )


def find_related_mie(connection, consulta: str, limit: int = 12) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM mie_range
        ORDER BY estacion, codigo_variable
        LIMIT 10000
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["estacion"]),
                normalize_text(row["codigo_variable"]),
                normalize_text(row["descripcion"]),
                normalize_text(row["formato"]),
                normalize_text(row["valor_target"]),
            ]
        ),
        limit,
    )


def find_helpful_feedback(connection, consulta: str, limit: int = 5) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM feedback
        WHERE funciono = 1
        ORDER BY fecha DESC, id DESC
        LIMIT 500
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["consulta"]),
                normalize_text(row["respuesta_ia"]),
                normalize_text(row["comentario"]),
            ]
        ),
        limit,
    )


def find_manual_knowledge(connection, consulta: str, limit: int = 5) -> list[dict]:
    rows = connection.execute(
        """
        SELECT *
        FROM conocimiento_manual
        ORDER BY fecha DESC, id DESC
        LIMIT 1000
        """
    ).fetchall()
    return _score_rows(
        rows,
        consulta,
        lambda row: " ".join(
            [
                normalize_text(row["area"]),
                normalize_text(row["estacion"]),
                normalize_text(row["componente"]),
                normalize_text(row["titulo"]),
                normalize_text(row["descripcion"]),
                normalize_text(row["solucion"]),
                normalize_text(row["causa_raiz"]),
                normalize_text(row["tags"]),
            ]
        ),
        limit,
    )


def find_parameter_details(connection, consulta: str, limit: int = 10) -> dict:
    code_match = re.search(r"\b(\d{2,4}-\d{3})\b", consulta)
    code = code_match.group(1) if code_match else None

    if code:
        parameters = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM mie_range
                WHERE codigo_variable = ?
                ORDER BY tipo, formato
                LIMIT ?
                """,
                (code, limit),
            ).fetchall()
        ]
        changes = [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM mie_cambios
                WHERE codigo_variable = ?
                ORDER BY fecha DESC, id DESC
                LIMIT 10
                """,
                (code,),
            ).fetchall()
        ]
        return {"codigo": code, "parametros": parameters, "cambios": changes}

    top_candidates = find_related_mie(connection, consulta, limit=limit)
    candidate_codes = []
    seen = set()
    for item in top_candidates:
        candidate_code = item.get("codigo_variable")
        if candidate_code and candidate_code not in seen:
            seen.add(candidate_code)
            candidate_codes.append(candidate_code)

    changes = []
    if candidate_codes:
        placeholders = ", ".join("?" for _ in candidate_codes)
        sql = f"""
            SELECT *
            FROM mie_cambios
            WHERE codigo_variable IN ({placeholders})
            ORDER BY fecha DESC, id DESC
            LIMIT 10
        """
        changes = [dict(row) for row in connection.execute(sql, tuple(candidate_codes)).fetchall()]
    return {"codigo": None, "parametros": top_candidates, "cambios": changes}


def _render_local_answer(
    consulta: str,
    paros: list[dict],
    rdis: list[dict],
    pm_cards: list[dict],
    mie: list[dict],
    feedback: list[dict],
    manual_knowledge: list[dict],
    parameter_details: dict,
    patterns: list[str],
    zone: str | None,
) -> str:
    lines = [f"Consulta: {consulta}"]
    if zone:
        lines.append(f"Zona activa: {zone}")

    if paros:
        first = paros[0]
        lines.append(f"Ha pasado antes: si, al menos {len(paros)} casos similares encontrados.")
        lines.append("Accion inmediata mas cercana: " + (first.get("accion_inmediata") or "sin accion inmediata documentada"))
        lines.append("Causa basica mas cercana: " + (first.get("causa_basica") or "sin causa basica documentada"))
    else:
        lines.append("Ha pasado antes: no se han encontrado casos similares en DDS.")

    if rdis:
        lines.append("Causa raiz documentada: " + (rdis[0].get("causa_raiz") or "no disponible"))
    if pm_cards:
        lines.append("Accion grave relacionada: " + (pm_cards[0].get("descripcion_accion") or "sin accion documentada"))
    if mie:
        labels = []
        for item in mie[:5]:
            labels.append(" / ".join(part for part in [item.get("codigo_variable"), item.get("descripcion"), item.get("formato")] if part))
        lines.append("Parametros MIE a revisar: " + "; ".join(label for label in labels if label))
    if feedback:
        lines.append("Solucion validada antes por feedback: " + (feedback[0].get("respuesta_ia") or "sin detalle"))
    if manual_knowledge:
        lines.append(
            "Conocimiento manual relacionado: "
            + (
                manual_knowledge[0].get("solucion")
                or manual_knowledge[0].get("descripcion")
                or manual_knowledge[0].get("titulo")
                or "sin detalle"
            )
        )
    if parameter_details.get("codigo") and parameter_details.get("parametros"):
        first = parameter_details["parametros"][0]
        lines.append(
            "Parametro identificado: "
            + " / ".join(
                part
                for part in [
                    first.get("codigo_variable"),
                    first.get("descripcion"),
                    first.get("valor_target"),
                    first.get("tolerancia_inf"),
                    first.get("tolerancia_sup"),
                ]
                if part
            )
        )
    if parameter_details.get("cambios"):
        last_change = parameter_details["cambios"][0]
        lines.append(
            "Ultimo cambio conocido: "
            + " / ".join(
                part
                for part in [
                    last_change.get("fecha"),
                    last_change.get("codigo_variable"),
                    last_change.get("descripcion_variable"),
                    last_change.get("valor_actual"),
                ]
                if part
            )
        )
    if patterns:
        lines.append("Patrones detectados:")
        lines.extend(f"- {pattern}" for pattern in patterns)
    return "\n".join(lines)


def _anthropic_answer(settings: Settings, prompt: str) -> str | None:
    if not settings.anthropic_api_key:
        return None
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.anthropic_model,
            "max_tokens": 900,
            "system": (
                "Eres el asistente tecnico experto de la linea MCM5 de fabricacion de panales adulto en Montornes. "
                "Responde en espanol, de forma directa y practica, usando solo el contexto proporcionado."
            ),
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get("content", [])
    texts = [item.get("text", "") for item in content if item.get("type") == "text"]
    return "\n".join(texts).strip() or None


def _openai_compatible_answer(
    *,
    api_url: str,
    api_key: str | None,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> str | None:
    if not api_key:
        return None
    response = requests.post(
        api_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices", [])
    if not choices:
        return None
    message = choices[0].get("message", {})
    return normalize_text(message.get("content")) or None


def _resolve_provider(settings: Settings, requested_provider: str | None) -> str:
    provider = (requested_provider or settings.default_provider or "auto").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        provider = "auto"
    if provider != "auto":
        return provider

    if settings.anthropic_api_key:
        return "anthropic"
    if settings.openai_api_key:
        return "openai"
    if settings.google_api_key:
        return "google"
    if settings.xai_api_key:
        return "xai"
    return "auto"


def _llm_answer(settings: Settings, prompt: str, requested_provider: str | None) -> tuple[str | None, str]:
    provider = _resolve_provider(settings, requested_provider)
    system_prompt = (
        "Eres el asistente tecnico experto de la linea MCM5 de fabricacion de panales adulto en Montornes. "
        "Responde en espanol, de forma directa y practica, usando solo el contexto proporcionado."
    )

    if provider == "anthropic":
        return _anthropic_answer(settings, prompt), provider
    if provider == "openai":
        return (
            _openai_compatible_answer(
                api_url="https://api.openai.com/v1/chat/completions",
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                system_prompt=system_prompt,
                user_prompt=prompt,
            ),
            provider,
        )
    if provider == "google":
        return (
            _openai_compatible_answer(
                api_url="https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                api_key=settings.google_api_key,
                model=settings.google_model,
                system_prompt=system_prompt,
                user_prompt=prompt,
            ),
            provider,
        )
    if provider == "xai":
        return (
            _openai_compatible_answer(
                api_url="https://api.x.ai/v1/chat/completions",
                api_key=settings.xai_api_key,
                model=settings.xai_model,
                system_prompt=system_prompt,
                user_prompt=prompt,
            ),
            provider,
        )
    return None, "local"


def build_consulta_response(
    connection,
    settings: Settings,
    consulta: str,
    top_k: int = 8,
    usar_llm: bool = True,
    provider: str | None = None,
    zona: str | None = None,
    contexto_extra: str | None = None,
) -> dict:
    paros = find_similar_paros(connection, consulta, limit=top_k)
    rdis = find_related_rdis(connection, consulta, limit=5)
    pm_cards = find_related_pm_cards(connection, consulta, limit=5)
    mie = find_related_mie(connection, consulta, limit=12)
    feedback = find_helpful_feedback(connection, consulta, limit=5)
    manual_knowledge = find_manual_knowledge(connection, consulta, limit=5)
    parameter_details = find_parameter_details(connection, consulta, limit=12)

    paros = _filter_by_zone(paros, zona, ("componente", "descripcion", "causa_basica", "accion_inmediata"))
    rdis = _filter_by_zone(rdis, zona, ("descripcion_problema", "redefinicion_problema", "maquina", "causa_raiz"))
    pm_cards = _filter_by_zone(pm_cards, zona, ("zona", "subzona", "componente", "descripcion_efecto", "descripcion_accion"))
    mie = _filter_by_zone(mie, zona, ("estacion", "codigo_variable", "descripcion", "formato"))
    feedback = _filter_by_zone(feedback, zona, ("consulta", "respuesta_ia", "comentario"))
    manual_knowledge = _filter_by_zone(
        manual_knowledge,
        zona,
        ("area", "estacion", "componente", "titulo", "descripcion", "solucion", "causa_raiz", "tags"),
    )

    if zona and parameter_details.get("parametros"):
        parameter_details = {
            **parameter_details,
            "parametros": _filter_by_zone(
                parameter_details.get("parametros", []),
                zona,
                ("estacion", "codigo_variable", "descripcion", "formato"),
            ),
            "cambios": _filter_by_zone(
                parameter_details.get("cambios", []),
                zona,
                ("descripcion_variable", "motivo", "comentarios"),
            ),
        }

    patterns = _build_patterns(paros, rdis, pm_cards, manual_knowledge)
    sources = _build_sources(paros, rdis, pm_cards, mie, feedback, manual_knowledge, parameter_details)

    prompt = (
        f"Consulta del tecnico: {consulta}\n\n"
        f"Zona activa del tecnico: {zona or 'todas'}\n\n"
        f"Contexto adicional del tecnico:\n{contexto_extra or 'sin contexto adicional'}\n\n"
        f"Casos DDS similares:\n{paros}\n\n"
        f"RDIs relacionados:\n{rdis}\n\n"
        f"PM Cards relacionadas:\n{pm_cards}\n\n"
        f"Parametros MIE relevantes:\n{mie}\n\n"
        f"Detalle de parametros detectados:\n{parameter_details}\n\n"
        f"Conocimiento manual de planta:\n{manual_knowledge}\n\n"
        f"Feedback historico que si funciono:\n{feedback}\n\n"
        f"Patrones detectados:\n{patterns}\n\n"
        "Responde con esta estructura:\n"
        "1. Ha pasado antes\n"
        "2. Accion inmediata recomendada\n"
        "3. Causa raiz mas probable\n"
        "4. Parametros MIE a verificar\n"
        "5. Patron repetitivo o alerta"
    )

    respuesta = None
    provider_used = "local"
    if usar_llm:
        try:
            respuesta, provider_used = _llm_answer(settings, prompt, provider)
        except Exception:
            respuesta = None
            provider_used = "local"

    if not respuesta:
        respuesta = _render_local_answer(
            consulta,
            paros,
            rdis,
            pm_cards,
            mie,
            feedback,
            manual_knowledge,
            parameter_details,
            patterns,
            zona,
        )
        provider_used = "local"

    return {
        "consulta": consulta,
        "respuesta": respuesta,
        "provider": provider_used,
        "zona_activa": zona,
        "fuentes": sources,
        "patrones": patterns,
        "contexto": {
            "paros_dds": paros,
            "rdis": rdis,
            "pm_cards": pm_cards,
            "mie_range": mie,
            "parametros": parameter_details,
            "conocimiento_manual": manual_knowledge,
            "feedback": feedback,
        },
    }
