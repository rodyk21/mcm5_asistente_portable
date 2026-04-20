from __future__ import annotations

from pathlib import Path

from app.config import Settings
from app.utils import normalize_text, slug_text


DOC_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".txt",
    ".rtf",
    ".xls",
    ".xlsx",
    ".xlsm",
}


def _candidate_roots(settings: Settings) -> list[Path]:
    workspace_dir = settings.workspace_dir.resolve()
    return [
        settings.dds_dir,
        settings.rdi_dir,
        settings.pm_dir,
        settings.mie_dir,
        workspace_dir,
    ]


def search_library(settings: Settings, query: str, limit: int = 50) -> list[dict]:
    query_slug = slug_text(query)
    results: list[dict] = []
    seen: set[str] = set()

    for root in _candidate_roots(settings):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in DOC_EXTENSIONS:
                continue
            path_str = str(path.resolve())
            path_slug = slug_text(path_str)
            if path_str in seen:
                continue
            if query_slug and query_slug not in path_slug:
                continue
            seen.add(path_str)
            results.append(
                {
                    "nombre": path.name,
                    "ruta": path_str,
                    "extension": path.suffix.lower(),
                    "carpeta": str(path.parent),
                    "categoria": _categorize(path),
                }
            )
            if len(results) >= limit:
                return results
    return results


def _categorize(path: Path) -> str:
    full = slug_text(str(path))
    name = slug_text(path.name)
    if "cva" in name or "cva" in full:
        return "cva"
    if "manual" in name or "manual" in full:
        return "manual"
    if "plano" in name or "drawing" in name:
        return "plano"
    if "nordson" in name or "nordson" in full:
        return "nordson"
    if "mie" in name or "bms" in name:
        return "mie"
    if "rdi" in name:
        return "rdi"
    return normalize_text(path.suffix.lower()).lstrip(".") or "documento"
